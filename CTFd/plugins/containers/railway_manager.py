"""
Railway-based container manager using Railway GraphQL API.
Creates one Railway service per user/team, exposes via TCP proxy for netcat access.
"""

import atexit
import time

import requests
from apscheduler.schedulers import SchedulerNotRunningError
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from CTFd.models import db
from .models import ContainerInfoModel

from .container_manager import ContainerException

RAILWAY_API_URL = "https://backboard.railway.com/graphql/v2"
DEPLOYMENT_POLL_INTERVAL = 5
DEPLOYMENT_TIMEOUT = 300  # 5 minutes


class RailwayContainerManager:
    """Railway API-based container manager. Creates services per user, exposes via TCP proxy."""

    def __init__(self, settings, app):
        self.settings = settings
        self.app = app
        self.token = settings.get("railway_api_token") or ""
        self.project_id = settings.get("railway_project_id") or ""
        self.environment_id = settings.get("railway_environment_id") or ""

        if not self.token or not self.project_id or not self.environment_id:
            return

        try:
            self.expiration_seconds = int(settings.get("container_expiration", 0)) * 60
        except (ValueError, AttributeError):
            self.expiration_seconds = 0

        EXPIRATION_CHECK_INTERVAL = 5
        if self.expiration_seconds > 0:
            self.expiration_scheduler = BackgroundScheduler()
            self.expiration_scheduler.add_job(
                func=self.kill_expired_containers,
                args=(app,),
                trigger="interval",
                seconds=EXPIRATION_CHECK_INTERVAL,
            )
            self.expiration_scheduler.start()
            atexit.register(lambda: self.expiration_scheduler.shutdown())

    def _graphql(self, query: str, variables: dict = None) -> dict:
        """Execute a GraphQL request against Railway API."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        resp = requests.post(RAILWAY_API_URL, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            msg = data["errors"][0].get("message", "Railway API error")
            raise ContainerException(f"Railway API: {msg}")

        return data.get("data", {})

    def kill_expired_containers(self, app: Flask):
        """Remove expired Railway services and DB records."""
        with app.app_context():
            containers = ContainerInfoModel.query.all()
            for container in containers:
                if container.expires - int(time.time()) < 0:
                    try:
                        self.kill_container(container.container_id)
                    except ContainerException:
                        pass
                    db.session.delete(container)
                    db.session.commit()

    def is_container_running(self, container_id: str) -> bool:
        """Check if a Railway service (by service_id) has an ACTIVE deployment."""
        query = """
        query serviceInstance($serviceId: String!, $environmentId: String!) {
            serviceInstance(serviceId: $serviceId, environmentId: $environmentId) {
                latestDeployment {
                    status
                }
            }
        }
        """
        try:
            data = self._graphql(
                query,
                {
                    "serviceId": container_id,
                    "environmentId": self.environment_id,
                },
            )
            si = data.get("serviceInstance")
            if not si:
                return False
            dep = si.get("latestDeployment")
            if not dep:
                return False
            return dep.get("status") == "ACTIVE"
        except Exception:
            return False

    def create_container(
        self,
        chal_id: str,
        team_id: str,
        user_id: str,
        image: str,
        port: int,
        command: str,
        volumes: str,
    ) -> tuple:
        """
        Create a Railway service from Docker image, wait for deployment, create TCP proxy.
        Returns (service_id, hostname, port) for nc hostname port.
        """
        service_name = f"ctfd-chal-{chal_id}-{team_id}-{int(time.time())}"

        # 1. Create service from Docker image
        mutation = """
        mutation serviceCreate($input: ServiceCreateInput!) {
            serviceCreate(input: $input) {
                id
                name
            }
        }
        """
        data = self._graphql(
            mutation,
            {
                "input": {
                    "projectId": self.project_id,
                    "name": service_name,
                    "source": {"image": image},
                }
            },
        )
        created = data.get("serviceCreate")
        if not created:
            raise ContainerException("Railway service creation failed")
        service_id = created["id"]

        # 2. Set optional start command via serviceInstanceUpdate (if challenge specifies one)
        if command:
            update_mutation = """
            mutation serviceInstanceUpdate(
                $serviceId: String!, $environmentId: String!, $input: ServiceInstanceUpdateInput!
            ) {
                serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input)
            }
            """
            try:
                self._graphql(
                    update_mutation,
                    {
                        "serviceId": service_id,
                        "environmentId": self.environment_id,
                        "input": {"startCommand": command},
                    },
                )
            except ContainerException:
                pass  # Proceed even if start command fails; image default may work

        # 3. Set PORT variable so app listens on Railway-provided port (or challenge port)
        # For binaries listening on a fixed port, we may need to set PORT=challenge_port
        # Railway exposes via TCP proxy to applicationPort, so the container must listen on that port
        # Most challenge images listen on a fixed port (e.g. 1234). We use that as applicationPort.

        # 4. Trigger deploy (serviceCreate may auto-deploy; if not, call serviceInstanceDeployV2)
        deploy_mutation = """
        mutation serviceInstanceDeployV2($serviceId: String!, $environmentId: String!) {
            serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId)
        }
        """
        self._graphql(
            deploy_mutation,
            {"serviceId": service_id, "environmentId": self.environment_id},
        )

        # 5. Poll until deployment is ACTIVE or CRASHED
        start = time.time()
        while time.time() - start < DEPLOYMENT_TIMEOUT:
            query = """
            query serviceInstance($serviceId: String!, $environmentId: String!) {
                serviceInstance(serviceId: $serviceId, environmentId: $environmentId) {
                    latestDeployment {
                        status
                    }
                }
            }
            """
            data = self._graphql(
                query,
                {"serviceId": service_id, "environmentId": self.environment_id},
            )
            si = data.get("serviceInstance")
            dep = si.get("latestDeployment") if si else None
            status = dep.get("status") if dep else None

            if status == "ACTIVE":
                break
            if status == "CRASHED" or status == "FAILED":
                try:
                    self.kill_container(service_id)
                except ContainerException:
                    pass
                raise ContainerException(
                    f"Railway deployment failed (status: {status}). Check image and port."
                )
            time.sleep(DEPLOYMENT_POLL_INTERVAL)

        else:
            try:
                self.kill_container(service_id)
            except ContainerException:
                pass
            raise ContainerException("Railway deployment timed out (5 minutes)")

        # 6. Create TCP proxy
        tcp_mutation = """
        mutation tcpProxyCreate($input: TCPProxyCreateInput!) {
            tcpProxyCreate(input: $input) {
                id
                domain
                proxyPort
            }
        }
        """
        tcp_data = self._graphql(
            tcp_mutation,
            {
                "input": {
                    "serviceId": service_id,
                    "environmentId": self.environment_id,
                    "applicationPort": port,
                }
            },
        )
        tcp = tcp_data.get("tcpProxyCreate")
        if not tcp:
            try:
                self.kill_container(service_id)
            except ContainerException:
                pass
            raise ContainerException("Railway TCP proxy creation failed")

        domain = tcp.get("domain", "")
        proxy_port = tcp.get("proxyPort")
        if not domain or proxy_port is None:
            try:
                self.kill_container(service_id)
            except ContainerException:
                pass
            raise ContainerException("Railway TCP proxy did not return domain/port")

        return (service_id, domain, str(proxy_port))

    def get_container_port(self, container_id: str) -> str | None:
        """Not used for Railway; hostname and port are stored at creation."""
        return None

    def get_images(self) -> list:
        """Railway does not list local images; return empty list."""
        return []

    def kill_container(self, container_id: str):
        """Delete the Railway service (and its TCP proxy)."""
        mutation = """
        mutation serviceDelete($id: String!) {
            serviceDelete(id: $id)
        }
        """
        try:
            self._graphql(mutation, {"id": container_id})
        except requests.exceptions.HTTPError:
            pass  # Service may already be gone
        except ContainerException:
            raise

    def is_connected(self) -> bool:
        """Check if Railway API is reachable and token is valid."""
        query = """
        query project($id: String!) {
            project(id: $id) {
                id
                name
            }
        }
        """
        try:
            self._graphql(query, {"id": self.project_id})
            return True
        except Exception:
            return False
