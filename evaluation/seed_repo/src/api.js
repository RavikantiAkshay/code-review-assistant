// JavaScript API file with various issues
// ISSUE COUNT: 8 issues

// Issue 1: Using var instead of let/const (READABILITY - LOW)
var apiUrl = "https://api.example.com";

// Issue 2: eval usage (SECURITY - HIGH)
function executeCode(codeString) {
    return eval(codeString);
}

// Issue 3: innerHTML assignment (SECURITY - HIGH)
function renderContent(elementId, htmlContent) {
    document.getElementById(elementId).innerHTML = htmlContent;
}

// Issue 4: Missing semicolons (READABILITY - LOW)
function getData() {
    const data = fetch(apiUrl)
    return data
}

// Issue 5: == instead of === (CORRECTNESS - MEDIUM)
function checkValue(val) {
    if (val == null) {
        return false;
    }
    if (val == "true") {
        return true;
    }
    return false;
}

// Issue 6: Unused variable (READABILITY - LOW)
function processUser(user) {
    const unusedVar = "this is never used";
    return {
        name: user.name,
        email: user.email
    };
}

// Issue 7: No error handling in async function (CORRECTNESS - MEDIUM)
async function fetchUser(userId) {
    const response = await fetch(`${apiUrl}/users/${userId}`);
    const data = await response.json();
    return data;
}

// Issue 8: Console.log left in code (READABILITY - LOW)
function debugFunction(value) {
    console.log("Debug value:", value);
    return value * 2;
}

// Issue 9: Nested callbacks (COMPLEXITY - MEDIUM)
function processData(callback) {
    getData(function (data) {
        transformData(data, function (transformed) {
            saveData(transformed, function (result) {
                callback(result);
            });
        });
    });
}

module.exports = {
    executeCode,
    renderContent,
    getData,
    checkValue,
    processUser,
    fetchUser,
    debugFunction,
    processData
};
