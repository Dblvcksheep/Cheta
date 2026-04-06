function showValidation() {
  document.getElementById("password-requirements").classList.remove("d-none");
}

function hideValidation() {
  document.getElementById("password-requirements").classList.add("d-none");
}

function validatePassword() {
  const password = document.getElementById("password1").value;

  // Check each requirement
  if (password.length >= 8) {
    document.getElementById("length").textContent = "✅ At least 8 characters";
    document.getElementById("length").style.color = "green";
  } else {
    document.getElementById("length").textContent = "❌ At least 8 characters";
    document.getElementById("length").style.color = "red";
  }

  if (/[A-Z]/.test(password)) {
    document.getElementById("uppercase").textContent = "✅ At least one uppercase letter";
    document.getElementById("uppercase").style.color = "green";
  } else {
    document.getElementById("uppercase").textContent = "❌ At least one uppercase letter";
    document.getElementById("uppercase").style.color = "red";
  }

  if (/\d/.test(password)) {
    document.getElementById("number").textContent = "✅ At least one number";
    document.getElementById("number").style.color = "green";
  } else {
    document.getElementById("number").textContent = "❌ At least one number";
    document.getElementById("number").style.color = "red";
  }

  // Special character
  if (/[!@#$%^&*(),.?:{}|<>]/.test(password)) {
    document.getElementById("special").textContent = "✅ At least one special character";
    document.getElementById("special").style.color = "green";
  } else {
    document.getElementById("special").textContent = "❌ At least one special character";
    document.getElementById("special").style.color = "red";
  }

  checkFormReady();
}

function checkMatch() {
  const password1 = document.getElementById("password1").value;
  const password2 = document.getElementById("password2").value;
  const message = document.getElementById("match-message");

  if (password2 === "") {
    message.textContent = "";
    message.className = "form-text";
  } else if (password1 === password2) {
    message.textContent = "✅ Passwords match";
    message.className = "form-text text-success";
  } else {
    message.textContent = "❌ Passwords do not match";
    message.className = "form-text text-danger";
  }

  checkFormReady();
}

function checkFormReady() {
  const password = document.getElementById("password1").value;
  const confirm = document.getElementById("password2").value;
  const submitBtn = document.getElementById("submitBtn");

  const valid =
    password.length >= 8 &&
    /[A-Z]/.test(password) &&
    /\d/.test(password) &&
    /[!@#$%^&*(),.?:{}|<>]/.test(password) &&
    password === confirm;

  submitBtn.disabled = !valid;
}
