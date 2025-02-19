async function postData() {
    try {
        const response = await fetch("https://jsonplaceholder.typicode.com/posts", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                title: "Test Title",
                body: "This is a test post.",
                userId: 1,
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const responseData = await response.json();
        console.log("Success:", responseData);
        return responseData;
    } catch (error) {
        console.error("Error:", error);
        return null;
    }
}
postData();