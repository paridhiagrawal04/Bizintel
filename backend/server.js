const { exec } = require("child_process");
const express = require("express");
const cors = require("cors");
const multer = require("multer");

const app = express();

app.use(cors());
app.use(express.json());

/* STORAGE CONFIGURATION */

const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        cb(null, "uploads/");
    },
    filename: function (req, file, cb) {
        cb(null, Date.now() + "-" + file.originalname);
    }
});

const upload = multer({ storage: storage });

/* TEST ROUTE */

app.get("/", (req, res) => {
    res.send("AI Business Analyzer Backend Running");
});

/* FILE UPLOAD ROUTE */

app.post("/upload", upload.single("file"), (req, res) => {

    if (!req.file) {
        return res.status(400).json({ message: "No file uploaded" });
    }

    const filePath = req.file.path;

    exec(`python analyze.py ${filePath}`, (error, stdout, stderr) => {

        if (error) {
            console.error(error);
            return res.status(500).json({ message: "Analysis failed" });
        }

        res.json({
            message: "File analyzed successfully",
            analysis: JSON.parse(stdout)
        });

    });

});

const PORT = 5000;

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});

