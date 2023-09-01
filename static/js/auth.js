const reloadAuthState = (lockerCode) => {
	fetch("/locker/" + lockerCode + "/state")
		.then((response) => response.json())
		.then((data) => {
			let currentState = "";
			if (data.status == "NO_STEP") {
				currentState = "Waiting";
				currentClass = "bullet-dark";
			} else if (data.status == "STEP_PIN") {
				currentState = "Recognizing Iris";
				currentClass = "bullet-yellow";
			} else if (data.status == "STEP_IRIS") {
				currentState = "Iris Recognized";
				currentClass = "bullet-green";
			} else {
				currentState = "";
				currentClass = "bullet-dark";
			}

			const stateElement = document.getElementById("locker_state");
			stateElement.innerHTML = currentState;

			const bulletElement = stateElement.parentElement;
			bulletElement.className = currentClass;
		});
};

document.addEventListener("DOMContentLoaded", () => {
	let lockerCode = document.getElementById("locker_code").textContent;
	reloadAuthState(lockerCode);

	setInterval(() => {
		reloadAuthState(lockerCode);
	}, 2000);
});
