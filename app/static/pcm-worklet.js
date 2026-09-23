"use strict";

class Pcm16Capture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.frame = new Int16Array(3200);
    this.offset = 0;
  }

  process(inputs) {
    const channels = inputs[0];
    if (!channels?.length) return true;
    for (let i = 0; i < channels[0].length; i++) {
      let sample = 0;
      for (const channel of channels) sample += channel[i] || 0;
      sample = Math.max(-1, Math.min(1, sample / channels.length));
      this.frame[this.offset++] = Math.round(sample * (sample < 0 ? 32768 : 32767));
      if (this.offset === this.frame.length) {
        this.port.postMessage(this.frame.buffer, [this.frame.buffer]);
        this.frame = new Int16Array(3200);
        this.offset = 0;
      }
    }
    return true;
  }
}

registerProcessor("pcm16-capture", Pcm16Capture);
