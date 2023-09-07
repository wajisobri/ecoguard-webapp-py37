window.addEventListener("load", function () {
	// Num pointer
	let curPointer = -1;

	// Get otp container
	const OTPContainer = document.querySelector("#pin_single");

	const OTPValueContainer = document.querySelector("#pin_full");

	const enterNumpad = document.querySelectorAll(".num-item");
	enterNumpad.forEach((item) => {
		item.addEventListener("click", (e) => {
			if (curPointer >= 3) return;

			const value = e.target.innerText;
			curIndex = Array.from(inputs).findIndex((input) => !input.value);
			curPointer = curPointer + 1;
			handleInput(inputs[curIndex], value, curIndex, inputs);
		});
	});

	const deleteNumpad = document.querySelector(".num-item-delete");
	deleteNumpad.addEventListener("click", (e) => {
		if (curPointer === -1) return;

		handleDelete(inputs[curPointer], curPointer, inputs);
		curPointer = curPointer - 1;
	});

	const resetButton = document.querySelector("#reset");
	resetButton.addEventListener("click", () => {
		inputs.forEach((input) => resetInput(input));
		inputs[0].focus();
		curPointer = -1;
	});

	const continueButton = document.querySelector("#submit");
	continueButton.addEventListener("click", (e) => {
		updateValue(inputs);
		// alert(OTPValueContainer.value);
		inputs.forEach((input) => resetInput(input));
		inputs[0].focus();
		curPointer = -1;

		if (OTPValueContainer.value.includes("*")) {
			Swal.fire({
				icon: "error",
				title: "Oops...",
				text: "Please enter the complete PIN",
			});
			return;
		}

		auth_pin_form = document.getElementById("auth_pin_form");
		auth_pin_form.submit();
	});

	// Focus first input
	const firstInput = OTPContainer.querySelector("input");
	firstInput.focus();

	// OTP Logic

	const updateValue = (inputs) => {
		OTPValueContainer.value = Array.from(inputs).reduce(
			(acc, curInput) => acc.concat(curInput.value ? curInput.value : "*"),
			""
		);
	};

	const isValidInput = (inputValue) => {
		return Number(inputValue) === 0 && inputValue !== "0" ? false : true;
	};

	const setInputValue = (inputElement, inputValue) => {
		inputElement.value = inputValue;
	};

	const resetInput = (inputElement) => {
		setInputValue(inputElement, "");
	};

	const focusNext = (inputs, curIndex) => {
		const nextElement =
			curIndex < inputs.length - 1 ? inputs[curIndex + 1] : inputs[curIndex];

		nextElement.focus();
		nextElement.select();
	};

	const focusPrev = (inputs, curIndex) => {
		const prevElement = curIndex > 0 ? inputs[curIndex - 1] : inputs[curIndex];

		prevElement.focus();
		prevElement.select();
	};

	const focusIndex = (inputs, index) => {
		const element =
			index < inputs.length - 1 ? inputs[index] : inputs[inputs.length - 1];

		element.focus();
		element.select();
	};

	const handleValidMultiInput = (
		inputElement,
		inputValue,
		curIndex,
		inputs
	) => {
		const inputLength = inputValue.length;
		const numInputs = inputs.length;

		const endIndex = Math.min(curIndex + inputLength - 1, numInputs - 1);
		const inputsToChange = Array.from(inputs).slice(curIndex, endIndex + 1);
		inputsToChange.forEach((input, index) =>
			setInputValue(input, inputValue[index])
		);
		focusIndex(inputs, endIndex);
	};

	const handleInput = (inputElement, inputValue, curIndex, inputs) => {
		if (!isValidInput(inputValue)) return handleInvalidInput(inputElement);
		if (inputValue.length === 1)
			handleValidSingleInput(inputElement, inputValue, curIndex, inputs);
		else handleValidMultiInput(inputElement, inputValue, curIndex, inputs);
	};

	const handleValidSingleInput = (
		inputElement,
		inputValue,
		curIndex,
		inputs
	) => {
		setInputValue(inputElement, inputValue.slice(-1));
		focusNext(inputs, curIndex);
	};

	const handleInvalidInput = (inputElement) => {
		resetInput(inputElement);
	};

	const handleKeyDown = (event, key, inputElement, curIndex, inputs) => {
		if (key === "Delete") {
			resetInput(inputElement);
			focusPrev(inputs, curIndex);
		}
		if (key === "ArrowLeft") {
			event.preventDefault();
			focusPrev(inputs, curIndex);
		}
		if (key === "ArrowRight") {
			event.preventDefault();
			focusNext(inputs, curIndex);
		}
	};

	const handleDelete = (inputElement, curIndex, inputs) => {
		resetInput(inputElement);
		focusPrev(inputs, curIndex);
	};

	const handleKeyUp = (event, key, inputElement, curIndex, inputs) => {
		if (key === "Backspace") focusPrev(inputs, curIndex);
	};

	const inputs = OTPContainer.querySelectorAll("input:not(#pin_full)");
	inputs.forEach((input, index) => {
		input.addEventListener("input", (e) =>
			handleInput(input, e.target.value, index, inputs)
		);

		input.addEventListener("keydown", (e) =>
			handleKeyDown(e, e.key, input, index, inputs)
		);

		input.addEventListener("keyup", (e) =>
			handleKeyUp(e, e.key, input, index, inputs)
		);

		input.addEventListener("focus", (e) => e.target.select());
	});
});
