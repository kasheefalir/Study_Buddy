const assert = require("node:assert/strict");
const world = require("../app/ui/static/classroom-world.js");
assert(world.canStand(168, 255));
const player = {x: 168, y: 255};
world.move(player, -500, 0);
assert(player.x >= 150, "Movement must not tunnel through a desk.");
world.move(player, 0, 500);
assert(player.y <= 265, "Movement must stop at the lower wall.");
assert(!world.canStand(275, 155), "The entrance notch is not floor.");
for (const zone of world.zones) {
  for (let x = zone.x; x <= zone.x + zone.w; x++) {
    for (let y = zone.y; y <= zone.y + zone.h; y++) {
      assert(world.canStand(x, y), "Every classmate destination must be unobstructed.");
    }
  }
}
assert(!world.canStand(168, 255, [{x: 168, y: 255}]), "Characters cannot occupy the same feet position.");
// Flood fill verifies all four keyboard interactions can be reached from spawn.
const queue = [{x: 168, y: 254}], seen = new Set(["168,254"]);
for (let index = 0; index < queue.length; index++) {
  const p = queue[index];
  for (const [dx, dy] of [[2, 0], [-2, 0], [0, 2], [0, -2]]) {
    const q = {x: p.x + dx, y: p.y + dy}, key = q.x + "," + q.y;
    if (!seen.has(key) && world.canStand(q.x, q.y)) {seen.add(key); queue.push(q);}
  }
}
for (const [x, y] of [[151,125], [128,265], [112,76], [242,87]]) {
  assert(queue.some(p => Math.hypot(p.x-x,p.y-y) <= 26), "An interaction is unreachable.");
}
console.log("Movement, collisions, wandering bounds, and interaction reachability passed.");
