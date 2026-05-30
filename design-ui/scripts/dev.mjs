import { spawn } from "node:child_process";

const processes = [
  spawn("npm", ["run", "dev:api"], { stdio: "inherit", shell: true }),
  spawn("npm", ["run", "dev:web"], { stdio: "inherit", shell: true })
];

const stop = (code = 0) => {
  for (const child of processes) {
    if (!child.killed) child.kill("SIGTERM");
  }
  process.exit(code);
};

process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));

for (const child of processes) {
  child.on("exit", (code) => {
    if (code && code !== 0) stop(code);
  });
}
