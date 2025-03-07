document.addEventListener("DOMContentLoaded", function () {
        const downloadButton = document.getElementById("download_pdf");

        if (downloadButton) {
            downloadButton.addEventListener("click", async function () {
                try {
                    await loadHtml2Pdf();

                    const mainForm = document.getElementById("main-form");

                    if (!mainForm) {
                        console.error("Form not found.");
                        return;
                    }

                    console.log("Download button clicked. Generating PDF...");

                    const currentDate = new Date();
                    const filename = `document_${currentDate.getFullYear()}_${currentDate.getMonth() + 1}_${currentDate.getDate()}_${currentDate.getHours()}${currentDate.getMinutes()}.pdf`;

                    const options = {
                        margin: 1,
                        filename: filename,
                        image: { type: "jpeg", quality: 0.98 },
                        html2canvas: { scale: 2 },
                        jsPDF: { unit: "in", format: "letter", orientation: "portrait" },
                    };

                    html2pdf().set(options).from(mainForm).save();
                } catch (error) {
                    console.error("Error:", error);
                }
            });
        } else {
            console.error("Download button not found.");
        }
    });

    function loadHtml2Pdf() {
        return new Promise((resolve, reject) => {
            if (typeof html2pdf !== "undefined") {
                console.log("html2pdf.js already loaded.");
                resolve();
                return;
            }

            console.log("Loading html2pdf.js...");
            const script = document.createElement("script");
            script.src = "https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js";
            script.onload = () => {
                console.log("html2pdf.js loaded successfully.");
                resolve();
            };
            script.onerror = () => reject(new Error("Failed to load html2pdf.js"));
            document.body.appendChild(script);
        });
    }