const fs = require("fs");
const path = require("path");

function copy(source, target) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(source, target);
}

fs.rmSync("dist", { recursive: true, force: true });
fs.mkdirSync(path.join("dist", "assets"), { recursive: true });
copy(path.join("src", "index.html"), path.join("dist", "index.html"));
copy(path.join("src", "main.js"), path.join("dist", "assets", "main.js"));
copy(path.join("src", "styles.css"), path.join("dist", "assets", "styles.css"));
