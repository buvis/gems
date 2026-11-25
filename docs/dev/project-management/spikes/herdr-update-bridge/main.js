import { View, div } from "gpui-kit";
import { checking, nextCommand, setShared, updates } from "herdr";

export default class UpdateProbe extends View {
  init(_props, cx) {
    if (checking()) return;
    cx.spawn(async (taskCx) => {
      for (;;) {
        const command = await nextCommand();
        // A fresh task context also stops an obsolete instance after reload.
        taskCx.notify();
        const match = /^probe-([0-9a-f]{32})$/.exec(command);
        if (!match) continue;
        setShared("sysup.update-probe", {
          schema: 1,
          nonce: match[1],
          state: updates(),
        });
      }
    });
  }

  render() {
    return div().child("sysup update probe");
  }
}
