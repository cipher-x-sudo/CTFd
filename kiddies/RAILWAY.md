# Running Kiddies on Railway (CTFd containers plugin)

Railway pulls challenge images from a container registry. Build the image, push it, then use that image name in CTFd.

## 1. Build the image

From this directory:

```bash
docker build -t kiddie-pwn .
```

## 2. Tag for your registry

Use your Docker Hub (or other registry) username and repo name:

```bash
# Replace YOUR_DOCKERHUB_USER with your Docker Hub username
docker tag kiddie-pwn:latest YOUR_DOCKERHUB_USER/kiddie-pwn:latest
```

Example: `docker tag kiddie-pwn:latest theflash2k/kiddie-pwn:latest`

## 3. Push to the registry

```bash
docker login
docker push YOUR_DOCKERHUB_USER/kiddie-pwn:latest
```

For a **private** image, use a registry Railway can access (e.g. Docker Hub with a token, or GitHub Container Registry) and ensure your Railway project has access if required.

## 4. Create the container challenge in CTFd

1. In CTFd admin, create a new challenge and choose type **container**.
2. In the **Image** field you’ll see a text box (Railway doesn’t list local images). Enter the full image name, e.g.:
   - `YOUR_DOCKERHUB_USER/kiddie-pwn:latest`
3. Set **Connect type** to **TCP** and **Port** to **8000** (matches the Dockerfile `EXPOSE 8000`).
4. Save. The plugin will deploy the image on Railway and give players a host:port to connect with `nc`.

Players connect with: `nc <hostname> <port>`.
