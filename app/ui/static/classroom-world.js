/* Feet coordinates in the 320 x 288 room. Shared by movement and its tests. */
(function (root) {
  const desks = [150, 214].flatMap(y => [32, 112, 192].map(x => ({x, y, w: 32, h: 48})));
  const obstacles = [
    ...desks, {x: 26, y: 87, w: 48, h: 32}, {x: 79, y: 87, w: 32, h: 32},
    {x: 208, y: 62, w: 16, h: 32}, {x: 226, y: 44, w: 32, h: 40},
    {x: 242, y: 116, w: 16, h: 32}, {x: 272, y: 192, w: 32, h: 32},
    {x: 252, y: 237, w: 48, h: 32}, {x: 143, y: 112, w: 16, h: 12},
  ];
  const zones = [{x: 80, y: 133, w: 16, h: 12}, {x: 238, y: 177, w: 14, h: 18}];
  function canStand(x, y, others = []) {
    if (x < 24 || x > 296 || y < 76 || y > 265) return false;
    // The entrance notch and lower wall are outside the walkable floor.
    if (y >= 120 && y < 140 && x > 280) return false;
    if (y >= 140 && y < 192 && x > 256) return false;
    return !obstacles.some(r => x + 6 > r.x && x - 6 < r.x + r.w && y + 3 > r.y && y - 3 < r.y + r.h)
      && !others.some(p => Math.abs(p.x - x) < 13 && Math.abs(p.y - y) < 9);
  }
  function move(actor, dx, dy, others = []) {
    const steps = Math.ceil(Math.max(Math.abs(dx), Math.abs(dy)));
    if (!steps) return false;
    const startX = actor.x, startY = actor.y;
    for (let i = 0; i < steps; i++) {
      if (canStand(actor.x + dx / steps, actor.y, others)) actor.x += dx / steps;
      if (canStand(actor.x, actor.y + dy / steps, others)) actor.y += dy / steps;
    }
    return actor.x !== startX || actor.y !== startY;
  }
  function destination(zone, random = Math.random) {
    return {x: zone.x + random() * zone.w, y: zone.y + random() * zone.h};
  }
  const api = {desks, obstacles, zones, canStand, move, destination};
  if (typeof module !== "undefined") module.exports = api;
  else root.ClassroomWorld = api;
})(typeof window !== "undefined" ? window : globalThis);
