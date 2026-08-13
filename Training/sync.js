const { exec } = require("child_process");
require("dotenv").config();

// Kredensial diambil dari environment (.env) — jangan hardcode di file
const esCalianaUsername = process.env.SYNC_ES_CALIANA_USERNAME || "";
const esCalianaPassword = process.env.SYNC_ES_CALIANA_PASSWORD || "";
const esCalianaIpPort = process.env.SYNC_ES_CALIANA_IPPORT || "";

const esSirenUsername = process.env.SYNC_ES_SIREN_USERNAME || "";
const esSirenPassword = process.env.SYNC_ES_SIREN_PASSWORD || "";
const esSirenIpPort = process.env.SYNC_ES_SIREN_IPPORT || "";

if (!esCalianaUsername || !esSirenIpPort) {
  console.error("Konfigurasi environment SYNC_ES_* belum lengkap. Cek file .env (lihat .env.example).");
  process.exit(1);
}

const esCaliana = `http://${encodeURIComponent(esCalianaUsername)}:${encodeURIComponent(esCalianaPassword)}@${esCalianaIpPort}`;
const esSiren = `http://${encodeURIComponent(esSirenUsername)}:${encodeURIComponent(esSirenPassword)}@${esSirenIpPort}`;

// JSON searchBody
const searchBody = {
  query: {
    bool: {
      must: [
        {
          range: {
            created_at: { gte: "now-180d/d" }
          }
        }
      ]
    }
  }
};

// Convert JSON to single-line string (Windows-safe)
const searchBodyStr = JSON.stringify(searchBody).replace(/"/g, '\\"');

// Perintah untuk menyalin data ke indeks 'socmed-instagram-comments' di server 'esSiren'
const cmdComments = `elasticdump --input="${esCaliana}/socmed-instagram-comments" --output="${esSiren}/socmed-instagram-comments" --type=data --limit=100 --searchBody="${searchBodyStr}"`;

// Perintah untuk menyalin data ke indeks 'socmed-instagram-posts' di server 'esSiren'
const cmdPosts = `elasticdump --input="${esCaliana}/socmed-instagram-comments" --output="${esSiren}/socmed-instagram-posts" --type=data --limit=100 --searchBody="${searchBodyStr}"`;

console.log("Running command for comments:");
console.log(cmdComments);
console.log("Running command for posts:");
console.log(cmdPosts);

// Menjalankan perintah untuk 'socmed-instagram-comments'
exec(cmdComments, (err, stdout, stderr) => {
  if (err) return console.error("ERROR in comments:", err);
  if (stdout) console.log("STDOUT in comments:", stdout);
  if (stderr) console.error("STDERR in comments:", stderr);
});

// Menjalankan perintah untuk 'socmed-instagram-posts'
exec(cmdPosts, (err, stdout, stderr) => {
  if (err) return console.error("ERROR in posts:", err);
  if (stdout) console.log("STDOUT in posts:", stdout);
  if (stderr) console.error("STDERR in posts:", stderr);
});
