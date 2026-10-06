/* Sprite coordinates and timings mirror college-student.json. */
window.StudentSprite = class StudentSprite {
  constructor(url) {
    this.image = new Image();
    this.ready = new Promise((resolve, reject) => {
      this.image.onload = resolve;
      this.image.onerror = () => reject(new Error("Student sprite could not load."));
    });
    this.image.src = url;
  }

  draw(context, x, y, {direction = "down", mode = "idle", time = 0, scale = 1} = {}) {
    if (!this.image.complete || !this.image.naturalWidth) return;
    const durations = mode === "walk" ? [140, 140, 140, 140] : [1000, 350, 1300, 130];
    let elapsed = time % durations.reduce((sum, value) => sum + value, 0);
    let frame = 0;
    while (elapsed >= durations[frame] && frame < durations.length - 1) elapsed -= durations[frame++];
    const column = frame + (mode === "walk" ? 4 : 0);
    const row = ["down", "left", "right", "up"].indexOf(direction);
    context.imageSmoothingEnabled = false;
    context.drawImage(this.image, column * 32, Math.max(0, row) * 32, 32, 32, x, y, 32 * scale, 32 * scale);
    return column;
  }
};
