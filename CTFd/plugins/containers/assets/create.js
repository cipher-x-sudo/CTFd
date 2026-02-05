CTFd.plugin.run((_CTFd) => {
    const $ = _CTFd.lib.$;
    const md = _CTFd.lib.markdown();
});

var containerImage = document.getElementById("container-image");
var containerImageDefault = document.getElementById("container-image-default");
var path = "/containers/api/images";

fetch(path, {
    method: "GET",
    headers: {
        "Accept": "application/json",
        "CSRF-Token": init.csrfNonce
    }
})
.then(response => {
    if (!response.ok) {
        // Handle error response
        return Promise.reject("Error fetching data");
    }
    return response.json();
})
.then(data => {
    if (data.error != undefined) {
        containerImageDefault.innerHTML = data.error;
    } else if (data.images.length === 0) {
        // Railway (or no local images): allow typing image name e.g. username/repo:tag
        var parent = containerImage.parentNode;
        var input = document.createElement("input");
        input.type = "text";
        input.className = "form-control";
        input.name = "image";
        input.id = "container-image";
        input.placeholder = "e.g. username/kiddie-pwn:latest";
        input.title = "Docker image to pull (e.g. from Docker Hub)";
        input.required = true;
        parent.replaceChild(input, containerImage);
    } else {
        for (var i = 0; i < data.images.length; i++) {
            var opt = document.createElement("option");
            opt.value = data.images[i];
            opt.innerHTML = data.images[i];
            containerImage.appendChild(opt);
        }
        containerImageDefault.innerHTML = "Choose an image...";
        containerImage.removeAttribute("disabled");
    }
    console.log(data);
})
.catch(error => {
    // Handle fetch error
    console.error(error);
});
