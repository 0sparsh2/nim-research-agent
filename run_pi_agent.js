const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const args = process.argv.slice(2);
const logStream = fs.createWriteStream(path.join(__dirname, "pi_runner.log"));

console.log("Launching pi agent with args:", args);
logStream.write(`--- Starting Pi Session ---\nArgs: ${JSON.stringify(args)}\n\n`);

const env = {
  ...process.env,
  PI_BEHAVIOR_CONTROL: "off",
  PI_TELEMETRY: "0",
  PI_OFFLINE: "1",
  PI_CODING_AGENT_DIR: "/tmp/pi_agent_test_dir"
};

const child = spawn(
  "node",
  [
    path.join(__dirname, "node_modules/@earendil-works/pi-coding-agent/dist/cli.js"),
    ...args
  ],
  {
    env,
    stdio: ["pipe", "pipe", "pipe"]
  }
);

// Prevent blocking on stdin by closing it or writing if prompted
child.stdin.end();

child.stdout.on("data", (data) => {
  const str = data.toString();
  process.stdout.write(str);
  logStream.write(str);
});

child.stderr.on("data", (data) => {
  const str = data.toString();
  process.stderr.write(str);
  logStream.write(str);
});

child.on("close", (code) => {
  console.log(`\nPi process exited with code ${code}`);
  logStream.write(`\n--- Session Finished (Exit Code: ${code}) ---\n`);
  logStream.end();
  process.exit(code);
});
