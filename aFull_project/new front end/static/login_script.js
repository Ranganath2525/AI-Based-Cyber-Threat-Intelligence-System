document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');

    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            // The form will now submit to the '/' route using the POST method,
            // and the Flask backend will handle the redirect.
        });
    }
});