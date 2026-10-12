import * as agnost from "agnostai";

const org = process.env.AGNOST_ORG_ID;
if (!org) throw new Error("Set AGNOST_ORG_ID");
agnost.init(org);

const conversationId = `k8-${Date.now()}`;
for (let n = 1; n <= 8; n++) {
  const i = agnost.begin({
    userId: "k8-ts", agentName: "bug-test", conversationId,
    input: `k8 USER message ${n} of 8`,
  });
  i.end(`k8 AGENT reply ${n} of 8`);
}
console.log(`queued 8 turns in ${conversationId}`);
await new Promise((r) => setTimeout(r, 3000));
await agnost.shutdown();
console.log("shutdown done");
