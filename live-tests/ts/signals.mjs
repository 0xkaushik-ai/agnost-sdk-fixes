import * as agnost from "agnostai";
agnost.init("00000000-0000-4000-8000-000000000000");
process.on("SIGTERM", () => {
  console.log("app: starting 500 ms cleanup (e.g. closing DB)");
  setTimeout(() => { console.log("app: cleanup finished"); process.exit(143); }, 500);
});
setTimeout(() => process.kill(process.pid, "SIGTERM"), 100);
setInterval(() => {}, 1000);
