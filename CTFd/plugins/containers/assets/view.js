CTFd._internal.challenge.data = undefined;

CTFd._internal.challenge.renderer = null;

CTFd._internal.challenge.preRender = function () {};

CTFd._internal.challenge.render = null;

CTFd._internal.challenge.postRender = function () {};

CTFd._internal.challenge.submit = function (preview) {
	var challenge_id = parseInt(CTFd.lib.$("#challenge-id").val());
	var submission = CTFd.lib.$("#challenge-input").val();

    let alert = resetAlert();

	var body = {
		challenge_id: challenge_id,
		submission: submission,
	};
	var params = {};
	if (preview) {
		params["preview"] = true;
	}

	return CTFd.api
		.post_challenge_attempt(params, body)
		.then(function (response) {
			if (response.status === 429) {
				// User was ratelimited but process response
				return response;
			}
			if (response.status === 403) {
				// User is not logged in or CTF is paused.
				return response;
			}
			return response;
		});
};

function mergeQueryParams(parameters, queryParameters) {
	if (parameters.$queryParameters) {
		Object.keys(parameters.$queryParameters).forEach(function (
			parameterName
		) {
			var parameter = parameters.$queryParameters[parameterName];
			queryParameters[parameterName] = parameter;
		});
	}

	return queryParameters;
}

function resetAlert() {
    let alert = document.getElementById("deployment-info");
    if (alert) {
        alert.innerHTML = "";
        alert.classList.remove("alert-danger");
    }
    return alert;
}

function getCsrfToken() {
    return (window.init && window.init.csrfNonce) || (typeof init !== "undefined" && init && init.csrfNonce) || "";
}

function showConfigError(alertEl) {
    if (alertEl) {
        alertEl.append("Page configuration error. Refresh and try again.");
        alertEl.classList.add("alert-danger");
    }
}

function showRequestFailed(alertEl, status) {
    if (alertEl) {
        alertEl.append(status != null
            ? "Request failed (" + status + "). Check that the CTF has started and your email is verified."
            : "Request failed. Try again or check the console.");
        alertEl.classList.add("alert-danger");
    }
}

function toggleChallengeCreate() {
    let btn = document.getElementById("create-chal");
    btn.classList.toggle('d-none');
}

function toggleChallengeUpdate() {
    let btn = document.getElementById("extend-chal");
    btn.classList.toggle('d-none');

    btn = document.getElementById("terminate-chal");
    btn.classList.toggle('d-none');
}

function calculateExpiry(date) {
    // Get the difference in minutes
    let difference = Math.ceil(
		(new Date(date * 1000) - new Date()) / 1000 / 60
	);;
    return difference;
}

function createChallengeLinkElement(data, parent) {

	var expires = document.createElement('span');
	expires.textContent = "Suffering ends in " + calculateExpiry(new Date(data.expires)) + " minutes.";

	parent.append(expires); 
	parent.append(document.createElement('br'));

	if (data.connect == "tcp") {
		let codeElement = document.createElement('code');
		codeElement.textContent = 'nc ' + data.hostname + " " + data.port;
		parent.append(codeElement);
    } else if(data.connect == "ssh") {
        let codeElement = document.createElement('code');
        // In case you have to get the password from other sources
        if(data.ssh_password == null) {
            codeElement.textContent = 'ssh -o StrictHostKeyChecking=no ' + data.ssh_username + '@' + data.hostname + " -p" + data.port;
        } else {
		    codeElement.textContent = 'sshpass -p' + data.ssh_password + " ssh -o StrictHostKeyChecking=no " + data.ssh_username + '@' + data.hostname + " -p" + data.port;
        }
		parent.append(codeElement);
	} else {
		let link = document.createElement('a');
		link.href = 'http://' + data.hostname + ":" + data.port;
		link.textContent = 'http://' + data.hostname + ":" + data.port;
		link.target = '_blank'
		parent.append(link);
	}
}

function view_container_info(challenge_id) {
    let alert = resetAlert();
    var csrfToken = getCsrfToken();
    if (!csrfToken) {
        showConfigError(alert);
        return;
    }
    var path = "/containers/api/view_info";
    fetch(path, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "CSRF-Token": csrfToken
        },
        body: JSON.stringify({ chal_id: challenge_id })
    })
    .then(response => response.json().catch(function () { return null; }).then(function (data) { return { response: response, data: data }; }))
    .then(function (_ref) {
        var response = _ref.response, data = _ref.data;
        if (!response.ok) {
            if (alert) {
                alert.append(data && (data.error || data.message) || ("Request failed (" + response.status + "). Check that the CTF has started and your email is verified."));
                alert.classList.add("alert-danger");
            }
            return;
        }
        if (data.status == "Suffering hasn't begun") {
            alert.append(data.status);
            toggleChallengeCreate();
        } else if (data.status == "already_running") {
            createChallengeLinkElement(data, alert);
            toggleChallengeUpdate();
        } else {
            resetAlert();
            if (alert) {
                alert.append(data.message || "Unknown error");
                alert.classList.add("alert-danger");
            }
            toggleChallengeUpdate();
        }
    })
    .catch(function (error) {
        console.error("Fetch error:", error);
        showRequestFailed(alert, null);
    });
}

function container_request(challenge_id) {
    let alert = resetAlert();
    var csrfToken = getCsrfToken();
    if (!csrfToken) {
        showConfigError(alert);
        return;
    }
    var path = "/containers/api/request";
    fetch(path, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "CSRF-Token": csrfToken
        },
        body: JSON.stringify({ chal_id: challenge_id })
    })
    .then(response => response.json().catch(function () { return null; }).then(function (data) { return { response: response, data: data }; }))
    .then(function (_ref) {
        var response = _ref.response, data = _ref.data;
        if (!response.ok) {
            if (alert) {
                alert.append(data && (data.error || data.message) || ("Request failed (" + response.status + "). Check that the CTF has started and your email is verified."));
                alert.classList.add("alert-danger");
            }
            toggleChallengeCreate();
            return;
        }
        if (data && data.error !== undefined) {
            alert.append(data.error);
            alert.classList.add("alert-danger");
            toggleChallengeCreate();
        } else if (data && data.message !== undefined) {
            alert.append(data.message);
            alert.classList.add("alert-danger");
            toggleChallengeCreate();
        } else {
            createChallengeLinkElement(data, alert);
            toggleChallengeUpdate();
            toggleChallengeCreate();
        }
    })
    .catch(function (error) {
        console.error("Fetch error:", error);
        showRequestFailed(alert, null);
    });
}

function container_renew(challenge_id) {
    let alert = resetAlert();
    var csrfToken = getCsrfToken();
    if (!csrfToken) {
        showConfigError(alert);
        return;
    }
    var path = "/containers/api/renew";
    fetch(path, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "CSRF-Token": csrfToken
        },
        body: JSON.stringify({ chal_id: challenge_id })
    })
    .then(response => response.json().catch(function () { return null; }).then(function (data) { return { response: response, data: data }; }))
    .then(function (_ref) {
        var response = _ref.response, data = _ref.data;
        if (!response.ok) {
            if (alert) {
                alert.append(data && (data.error || data.message) || ("Request failed (" + response.status + "). Check that the CTF has started and your email is verified."));
                alert.classList.add("alert-danger");
            }
            toggleChallengeCreate();
            return;
        }
        if (data && data.error !== undefined) {
            alert.append(data.error);
            alert.classList.add("alert-danger");
            toggleChallengeCreate();
        } else if (data && data.message !== undefined) {
            alert.append(data.message);
            alert.classList.add("alert-danger");
            toggleChallengeCreate();
        } else {
            createChallengeLinkElement(data, alert);
        }
    })
    .catch(function (error) {
        console.error("Fetch error:", error);
        showRequestFailed(alert, null);
    });
}

function container_stop(challenge_id) {
    let alert = resetAlert();
    var csrfToken = getCsrfToken();
    if (!csrfToken) {
        showConfigError(alert);
        return;
    }
    var path = "/containers/api/stop";
    fetch(path, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "CSRF-Token": csrfToken
        },
        body: JSON.stringify({ chal_id: challenge_id })
    })
    .then(response => response.json().catch(function () { return null; }).then(function (data) { return { response: response, data: data }; }))
    .then(function (_ref) {
        var response = _ref.response, data = _ref.data;
        if (!response.ok) {
            if (alert) {
                alert.append(data && (data.error || data.message) || ("Request failed (" + response.status + "). Check that the CTF has started and your email is verified."));
                alert.classList.add("alert-danger");
            }
            toggleChallengeCreate();
            return;
        }
        if (data && data.error !== undefined) {
            alert.append(data.error);
            alert.classList.add("alert-danger");
            toggleChallengeCreate();
        } else if (data && data.message !== undefined) {
            alert.append(data.message);
            alert.classList.add("alert-danger");
            toggleChallengeCreate();
        } else {
            alert.append("You have suffered enough.");
            toggleChallengeCreate();
            toggleChallengeUpdate();
        }
    })
    .catch(function (error) {
        console.error("Fetch error:", error);
        showRequestFailed(alert, null);
    });
}

