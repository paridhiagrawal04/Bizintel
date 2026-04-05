const { exec } = require("child_process");
const express = require("express");
const cors = require("cors");
const multer = require("multer");
const path = require("path");
const fs = require("fs");

const app = express();

app.use(cors());
app.use(express.json());

// ─────────────────────────────────────────────
// STORAGE CONFIGURATION
// WHY: We use diskStorage (not memoryStorage) because Python needs
//      a real file path on disk — it can't read from a memory buffer.
//      We timestamp the filename to avoid collisions when two users
//      upload files with the same name simultaneously.
// ─────────────────────────────────────────────
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        const uploadDir = "uploads/";

        // Create the uploads folder if it doesn't exist yet
        // WHY: If someone deletes the folder or runs the server fresh,
        //      Multer would crash without this safety check.
        if (!fs.existsSync(uploadDir)) {
            fs.mkdirSync(uploadDir);
        }

        cb(null, uploadDir);
    },
    filename: function (req, file, cb) {
        cb(null, Date.now() + "-" + file.originalname);
    }
});

// ─────────────────────────────────────────────
// FILE TYPE FILTER
// WHY: We validate BEFORE the file is saved to disk.
//      This prevents junk files (PDFs, images, etc.) from
//      ever reaching Python, giving the user a clear error message.
// ─────────────────────────────────────────────
const allowedExtensions = [".xlsx", ".xls", ".csv"];

const fileFilter = function (req, file, cb) {
    const ext = path.extname(file.originalname).toLowerCase();

    if (allowedExtensions.includes(ext)) {
        cb(null, true); // Accept the file
    } else {
        cb(
            new Error(
                `Invalid file type '${ext}'. Only .xlsx, .xls, and .csv files are allowed.`
            ),
            false // Reject the file
        );
    }
};

const upload = multer({ storage, fileFilter });

// ─────────────────────────────────────────────
// HELPER — Delete uploaded file after use
// WHY: We don't need to keep the file on the server after analysis.
//      Leaving files around wastes disk space and is a privacy risk.
//      We use fs.unlink and swallow any error silently — cleanup
//      failure is non-critical and should not affect the response.
// ─────────────────────────────────────────────
function cleanupFile(filePath) {
    fs.unlink(filePath, (err) => {
        if (err) console.warn("Could not delete temp file:", filePath);
    });
}

// ─────────────────────────────────────────────
// TEST ROUTE
// ─────────────────────────────────────────────
app.get("/", (req, res) => {
    res.send("BizIntel Backend Running ✓");
});

// ─────────────────────────────────────────────
// FILE UPLOAD + ANALYSIS ROUTE
// ─────────────────────────────────────────────
app.post("/upload", upload.single("file"), (req, res) => {

    // — Guard: no file attached —
    if (!req.file) {
        return res.status(400).json({ message: "No file uploaded." });
    }

    const filePath = req.file.path;

    // WHY we quote the path: file names with spaces would break
    // the shell command without quotes around the path argument.
    exec(`python analyze.py "${filePath}"`, (error, stdout, stderr) => {

        // Always clean up the file regardless of success or failure
        cleanupFile(filePath);

        // — Guard: process-level failure (Python not found, syntax error, etc.) —
        if (error) {
            console.error("exec error:", error.message);
            console.error("stderr:", stderr);
            return res.status(500).json({
                message: "Analysis process failed. Check server logs."
            });
        }

        // — Guard: empty output —
        // WHY: If Python prints nothing (e.g. silent crash), JSON.parse
        //      would throw an unhandled exception and crash Node.
        if (!stdout || stdout.trim() === "") {
            return res.status(500).json({
                message: "Python returned no output."
            });
        }

        // — Parse Python's JSON output —
        let analysis;
        try {
            analysis = JSON.parse(stdout);
        } catch (parseErr) {
            console.error("JSON parse error:", parseErr.message);
            console.error("Raw stdout:", stdout);
            return res.status(500).json({
                message: "Could not parse analysis output."
            });
        }

        // — Guard: Python reported a data/validation error —
        // WHY: Our analyze.py always returns {"error": "..."} on failure
        //      instead of crashing. We surface that message to the frontend.
        if (analysis.error) {
            return res.status(422).json({
                message: analysis.error
            });
        }

        // — Success —
        return res.status(200).json({
            message: "File analyzed successfully",
            analysis
        });
    });
});

// ─────────────────────────────────────────────
// MULTER ERROR HANDLER (file type rejection, size limits, etc.)
// WHY: Multer errors don't automatically reach Express's default
//      error handler in all versions. This middleware catches them
//      and returns a clean JSON response instead of an HTML crash page.
// ─────────────────────────────────────────────
app.use((err, req, res, next) => {
    if (err) {
        return res.status(400).json({ message: err.message });
    }
    next();
});

// ─────────────────────────────────────────────
// START SERVER
// ─────────────────────────────────────────────
const PORT = 5000;

app.listen(PORT, () => {
    console.log(`BizIntel server running on http://localhost:${PORT}`);
});