import { runCommand } from "./home-assistant-client";

describe("Home Assistant command output", () => {
  it("captures logs larger than the default one MiB buffer", () => {
    const output = runCommand(process.execPath, ["-e", "process.stdout.write('x'.repeat(2 * 1024 * 1024))"]);
    expect(output.length).toBe(2 * 1024 * 1024);
  });

  it("reports exit status and stderr without exposing stdout", () => {
    expect(() => runCommand(process.execPath, ["-e", "console.log('private response'); console.error('diagnostic failure'); process.exit(7)"]))
      .toThrow(`${process.execPath} failed (exit 7): diagnostic failure`);
  });
});
