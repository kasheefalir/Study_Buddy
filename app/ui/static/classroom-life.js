/* Navigation and preloaded classmate facts never call the conversational agent. */
window.ClassroomLife = class ClassroomLife {
  constructor({room, selectedId, open, name}) {
    this.room = room; this.open = open; this.name = name;
    this.player = {x: 168, y: 255, direction: "down", moving: false};
    this.keys = new Set(); this.npcs = []; this.facts = []; this.documentId = null;
    this.last = 0; this.active = null;
    this.targets = [
      {id: "chat", label: "Talk to Professor", x: 151, y: 125},
      {id: "chat", label: "Study at your desk", x: 128, y: 265},
      {id: "context", label: "Read the chalkboard", x: 112, y: 76},
      {id: "materials", label: "Open study materials", x: 242, y: 87},
    ];
    this.setClassmates(selectedId);
    document.addEventListener("keydown", event => {
      if (document.querySelector("dialog[open]") || event.target.closest("input, textarea, select, [contenteditable=true]") || event.altKey || event.ctrlKey || event.metaKey) return;
      if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) {
        event.preventDefault();
        // A short tap must still move even when keyup arrives between frames.
        if (!event.repeat && !this.keys.has(event.key)) {
          const [dx, dy, direction] = {ArrowUp: [0,-1,"up"], ArrowDown: [0,1,"down"], ArrowLeft: [-1,0,"left"], ArrowRight: [1,0,"right"]}[event.key];
          this.player.direction = direction;
          ClassroomWorld.move(this.player, dx * 2, dy * 2, this.npcs);
        }
        this.keys.add(event.key); this.room.querySelector("canvas").focus({preventScroll: true});
      } else if (event.code === "Space" && !event.target.closest("button,a")) {
        event.preventDefault();
        if (!event.repeat && this.active) this.interact(this.active);
      }
    });
    document.addEventListener("keyup", event => this.keys.delete(event.key));
    window.addEventListener("blur", () => this.pause());
    document.addEventListener("visibilitychange", () => this.pause());
    document.querySelector("#nearby-action").onclick = () => {if (this.active) this.interact(this.active)};
  }
  pause() {this.keys.clear(); this.player.moving = false;}
  setClassmates(selectedId) {
    this.npcs.forEach(npc => npc.button.remove());
    this.npcs = StudentCharacters.filter(c => c.id !== selectedId).slice(0, 2).map((character, index) => {
      const zone = ClassroomWorld.zones[index];
      const spawn = [{x: zone.x + zone.w / 2, y: zone.y + zone.h / 2},
        {x: zone.x, y: zone.y}, {x: zone.x + zone.w, y: zone.y + zone.h}]
        .find(point => ClassroomWorld.canStand(point.x, point.y, [this.player]));
      if (!spawn) return null;
      const npc = {...character, zone, ...spawn,
        direction: "down", moving: false, wait: 2 + index, target: null,
        sprite: new StudentSprite("/static/characters/" + character.file + ".png")};
      npc.sprite.ready.catch(() => {npc.button.hidden = true});
      const button = document.createElement("button");
      button.className = "classmate-hotspot"; button.setAttribute("aria-label", "Talk to " + character.name);
      const marker = document.createElement("span");
      marker.className = "interaction-marker"; marker.textContent = "..."; marker.setAttribute("aria-hidden", "true");
      button.append(marker);
      button.onclick = () => this.interact(npc);
      npc.button = button; this.room.append(button); return npc;
    }).filter(Boolean);
  }
  // Facts are generated at ingestion; interaction only reads the session's cache.
  setFacts({documentId, documentIds = [documentId], facts}) {
    this.documentId = documentId;
    this.facts = Array.isArray(facts) ? facts.filter(f => documentIds.includes(f.documentId) && typeof f.text === "string" && f.text.trim() && typeof f.source === "string" && f.source.trim()) : [];
  }
  fact(npc) {
    const index = this.npcs.indexOf(npc);
    return this.facts.length ? this.facts[Math.max(0, index) % this.facts.length] : null;
  }
  interact(target) {
    this.pause();
    if (target.button) {
      const fact = this.fact(target);
      document.querySelector("#classmate-name").textContent = target.name;
      document.querySelector("#classmate-fact").textContent = fact?.text || "I'll have something to share when your study material is ready.";
      document.querySelector("#classmate-source").textContent = fact?.source || "Document facts are not loaded yet.";
      this.open("classmate");
    } else this.open(target.id);
  }
  update(now, reducedMotion) {
    const dt = this.last ? Math.min((now - this.last) / 1000, .05) : 0;
    this.last = now;
    if (document.hidden || document.querySelector("dialog[open]")) {this.pause(); return;}
    const p = this.player;
    const key = [...this.keys].at(-1);
    const vectors = {ArrowUp: [0, -1, "up"], ArrowDown: [0, 1, "down"], ArrowLeft: [-1, 0, "left"], ArrowRight: [1, 0, "right"]};
    p.moving = false;
    if (vectors[key]) {
      const [dx, dy, direction] = vectors[key]; p.direction = direction;
      p.moving = ClassroomWorld.move(p, dx * 46 * dt, dy * 46 * dt, this.npcs);
    }
    for (const npc of this.npcs) {
      npc.moving = false;
      if (reducedMotion) continue;
      npc.wait -= dt;
      if (!npc.target && npc.wait <= 0) npc.target = ClassroomWorld.destination(npc.zone);
      if (npc.target) {
        const dx = npc.target.x - npc.x, dy = npc.target.y - npc.y;
        if (Math.abs(dx) + Math.abs(dy) < 1) {
          npc.target = null; npc.wait = 3 + Math.random() * 5;
        } else {
          const horizontal = Math.abs(dx) > .5;
          const amount = horizontal ? dx : dy;
          npc.direction = horizontal ? (dx > 0 ? "right" : "left") : (dy > 0 ? "down" : "up");
          const delta = Math.sign(amount) * Math.min(Math.abs(amount), 14 * dt);
          npc.moving = ClassroomWorld.move(npc, horizontal ? delta : 0, horizontal ? 0 : delta, [p, ...this.npcs.filter(other => other !== npc)]);
          if (!npc.moving) {npc.target = null; npc.wait = 2;}
        }
      }
    }
    const available = [...this.targets, ...this.npcs].map(t => ({target: t, distance: Math.hypot(t.x - p.x, t.y - p.y)})).filter(t => t.distance <= 26).sort((a, b) => a.distance - b.distance);
    this.active = available[0]?.target || null;
    const action = document.querySelector("#nearby-action");
    action.hidden = !this.active;
    if (this.active) action.textContent = (this.active.label || "Talk to " + this.active.name) + " · Space";
    const label = document.querySelector(".student-label");
    label.textContent = this.name || "YOU";
    label.style.left = p.x / 320 * 100 + "%";
    label.style.top = (p.y + 3) / 288 * 100 + "%";
    for (const npc of this.npcs) {
      Object.assign(npc.button.style, {left: (npc.x - 10) / 320 * 100 + "%", top: (npc.y - 30) / 288 * 100 + "%", width: "6.25%", height: 30 / 288 * 100 + "%"});
    }
  }
  actors(context, student, time, reducedMotion) {
    return [...this.npcs.map(npc => ({y: npc.y, draw: () => npc.sprite.draw(context, Math.round(npc.x - 16), Math.round(npc.y - 30), {direction: npc.direction, mode: npc.moving ? "walk" : "idle", time: reducedMotion ? 0 : time})})),
      {y: this.player.y, draw: () => student.draw(context, Math.round(this.player.x - 16), Math.round(this.player.y - 30), {direction: this.player.direction, mode: this.player.moving ? "walk" : "idle", time: reducedMotion ? 0 : time})}];
  }
};
