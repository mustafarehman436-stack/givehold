import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type Item = {
  id: number;
  name: string;
  category: string;
  condition: string;
  on_hand: number;
  reserved: number;
  available: number;
};
type Pickup = {
  id: string;
  volunteer_id: number;
  status: string;
  fulfilled_at: string | null;
};
type Reservation = {
  item_name: string;
  id: number;
  pickup_id: string;
  item_id: number;
  quantity: number;
  status: string;
};
type Volunteer = { id: number; name: string };
class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
async function api(path: string, body?: unknown, method = "POST") {
  const response = await fetch(
    "/api" + path,
    body === undefined
      ? {}
      : {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const data = await response.json();
  if (!response.ok)
    throw new ApiError(
      response.status,
      typeof data.detail === "string" ? data.detail : "Check the form values.",
    );
  return data;
}
function App() {
  const [items, setItems] = useState<Item[]>([]),
    [pickups, setPickups] = useState<Pickup[]>([]),
    [reservations, setReservations] = useState<Reservation[]>([]),
    [volunteers, setVolunteers] = useState<Volunteer[]>([]);
  const [view, setView] = useState("Inventory"),
    [volunteer, setVolunteer] = useState(1),
    [pickup, setPickup] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [loaded, setLoaded] = useState(false),
    [editing, setEditing] = useState<Item | null>(null),
    [showForm, setShowForm] = useState(false),
    [search, setSearch] = useState("");
  const guard = useRef(false);
  const [offset, setOffset] = useState(0);
  const [inventoryLoading, setInventoryLoading] = useState(false);
  const [inventory, setInventory] = useState({total: 0, on_hand: 0, reserved: 0, available: 0});
  const inventoryRequest = useRef(0);
  async function refreshInventory() {
    const request = ++inventoryRequest.current;
    setInventoryLoading(true);
    try {
      const data = await api(`/inventory?limit=50&offset=${offset}&q=${encodeURIComponent(search)}`);
      if (request === inventoryRequest.current) {
        setItems(data.items);
        setInventory(data);
      }
    } finally {
      if (request === inventoryRequest.current) setInventoryLoading(false);
    }
  }
  useEffect(() => {
    const timer = window.setTimeout(() => {
      refreshInventory().catch((e) => setMessage(e.message));
    }, 200);
    return () => { window.clearTimeout(timer); inventoryRequest.current++; };
  }, [offset, search]);
  async function refresh() {
    const [, b, c, d] = await Promise.all([
      refreshInventory(),
      api("/pickups"),
      api("/reservations"),
      api("/volunteers"),
    ]);
    setPickups(b);
    setReservations(c);
    setVolunteers(d);
    setLoaded(true);
  }
  useEffect(() => {
    refresh().catch((e) => setMessage(e.message));
  }, []);
  useEffect(() => {
    setPickup((current) =>
      pickups.some(
        (p) =>
          p.id === current &&
          p.volunteer_id === volunteer &&
          p.status === "open",
      )
        ? current
        : pickups.find(
            (p) => p.volunteer_id === volunteer && p.status === "open",
          )?.id || "",
    );
  }, [volunteer, pickups]);
  async function action(fn: () => Promise<unknown>, success: string) {
    if (guard.current) return;
    guard.current = true;
    setBusy(true);
    setMessage("");
    try {
      await fn();
      setMessage(success);
      await refresh();
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "Request failed. Retry safely.",
      );
    } finally {
      guard.current = false;
      setBusy(false);
    }
  }
  async function reserve(item: Item, quantity: number) {
    // Keep uncertain requests across refreshes in this tab. A different payload
    // gets its own key, so changing forms cannot discard an unresolved retry.
    const storageKey =
      "shelterstock:reserve:" + JSON.stringify([pickup, item.id, quantity]);
    const requestKey =
      sessionStorage.getItem(storageKey) || crypto.randomUUID();
    sessionStorage.setItem(storageKey, requestKey);
    try {
      await api("/reservations", {
        request_key: requestKey,
        pickup_id: pickup,
        item_id: item.id,
        quantity,
      });
      sessionStorage.removeItem(storageKey);
    } catch (e) {
      if (e instanceof ApiError && e.status < 500)
        sessionStorage.removeItem(storageKey);
      throw e;
    }
  }
  async function createPickup() {
    const storageKey = "shelterstock:pickup:" + volunteer;
    const id = sessionStorage.getItem(storageKey) || crypto.randomUUID();
    sessionStorage.setItem(storageKey, id);
    try {
      await api("/pickups", { id, volunteer_id: volunteer });
      sessionStorage.removeItem(storageKey);
    } catch (e) {
      if (e instanceof ApiError && e.status < 500)
        sessionStorage.removeItem(storageKey);
      throw e;
    }
  }
  const own = pickups.filter((p) => p.volunteer_id === volunteer);
  const visibleItems = items;
  return (
    <div className="shell">
      <aside>
        <a className="brand" href="/">
          GiveHold<span>Inventory operations</span>
        </a>
        <nav aria-label="Workspace">
          {["Inventory", "Reservations", "Pickups"].map((v) => (
            <button
              className={v === view ? "selected" : ""}
              aria-current={v === view ? "page" : undefined}
              key={v}
              onClick={() => setView(v)}
            >
              {v}
            </button>
          ))}
        </nav>
        <div className="side-note">
          Demo workspace
          <br />
          <span>Fictional records only</span>
        </div>
      </aside>
      <main>
        <header>
          <span>
            Workspace <span className="separator">/</span> {view}
          </span>
          <label>
            Volunteer
            <select
              value={volunteer}
              disabled={busy}
              onChange={(e) => setVolunteer(+e.target.value)}
            >
              {volunteers.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </label>
        </header>
        <div className="heading">
          <div>
            <h1>{view}</h1>
            <p>
              {view === "Inventory"
                ? "Review stock and reserve units for an open pickup."
                : view === "Reservations"
                  ? "Manage reservations for the selected volunteer."
                  : "Collect reserved items and review pickup history."}
            </p>
          </div>
          <div className="heading-actions">
            <button
              className="secondary"
              disabled={busy}
              onClick={() => action(async () => {}, "Records refreshed.")}
            >
              Refresh
            </button>
            <button
              disabled={busy}
              onClick={() => {
                if (view === "Inventory") {
                  setEditing(null);
                  setShowForm(true);
                } else action(createPickup, "Pickup created.");
              }}
            >
              {view === "Inventory" ? "Add item" : "New pickup"}
            </button>
          </div>
        </div>
        {view === "Inventory" && (
          <section className="stats" aria-label="Total inventory units">
            <div>
              <small>ON HAND</small>
              <strong>{inventory.on_hand}</strong>
            </div>
            <div>
              <small>RESERVED</small>
              <strong>{inventory.reserved}</strong>
            </div>
            <div>
              <small>AVAILABLE</small>
              <strong>{inventory.available}</strong>
            </div>
          </section>
        )}
        {(message || !loaded) && (
          <div className="notice" role="status">
            {message || "Loading inventory…"}
          </div>
        )}
        {view === "Inventory" && (
          <>
            <div className="toolbar">
              <label className="search">
                <span className="sr-only">Search inventory</span>
                <input
                  type="search"
                  disabled={busy}
                  placeholder="Search items or categories"
                  value={search}
                  onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
                />
              </label>
              <label>
                Reserve for
                <select
                  value={pickup}
                  onChange={(e) => setPickup(e.target.value)}
                >
                  <option value="">Choose an open pickup</option>
                  {own
                    .filter((p) => p.status === "open")
                    .map((p) => (
                      <option value={p.id} key={p.id}>
                        Pickup {p.id.slice(-8)}
                      </option>
                    ))}
                </select>
              </label>
            </div>
            <div className="table-wrap inventory-table">
              <table>
                <caption className="sr-only">
                  Inventory quantities and reservation actions
                </caption>
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>Category</th>
                    <th>Condition</th>
                    <th className="number">On hand</th>
                    <th className="number">Reserved</th>
                    <th className="number">Available</th>
                    <th>Reserve units</th>
                    <th>
                      <span className="sr-only">Edit item</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visibleItems.map((i) => (
                    <tr key={i.id}>
                      <td>
                        <span className="item-name">{i.name}</span>
                        <small className="mono">
                          ITM-{String(i.id).padStart(3, "0")}
                        </small>
                      </td>
                      <td>{i.category}</td>
                      <td className="condition">{i.condition}</td>
                      <td className="number">{i.on_hand}</td>
                      <td className="number muted">{i.reserved}</td>
                      <td
                        className={
                          "number available " + (!i.available ? "zero" : "")
                        }
                      >
                        {i.available}
                      </td>
                      <td>
                        <form
                          className="reserve-form"
                          onSubmit={(e) => {
                            e.preventDefault();
                            const quantity = Number(
                              new FormData(e.currentTarget).get("quantity"),
                            );
                            action(
                              () => reserve(i, quantity),
                              "Reservation saved.",
                            );
                          }}
                        >
                          <input
                            name="quantity"
                            aria-label={"Quantity for " + i.name}
                            type="number"
                            min="1"
                            max="1000000"
                            defaultValue="1"
                            required
                          />
                          <button
                            className="secondary"
                            disabled={busy || !pickup || !i.available}
                          >
                            Reserve
                          </button>
                        </form>
                      </td>
                      <td>
                        <button
                          className="link"
                          aria-label={"Edit " + i.name}
                          onClick={() => {
                            setEditing(i);
                            setShowForm(true);
                          }}
                        >
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {loaded && !visibleItems.length && (
                <p className="empty-state">
                  {search
                    ? "No matching items."
                    : "No inventory yet. Add an item to begin."}
                </p>
              )}
            </div>
            <div className="table-footer">
              <span>
                {inventory.total ? offset + 1 : 0}–{offset + items.length} of {inventory.total} items
              </span>
              <div>
                <button className="secondary" disabled={busy || inventoryLoading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button>{" "}
                <button className="secondary" disabled={busy || inventoryLoading || offset + items.length >= inventory.total} onClick={() => setOffset(offset + 50)}>Next</button>
              </div>
            </div>
            {!pickup && loaded && (
              <p className="context-note">
                Create an open pickup in Pickups to reserve items.
              </p>
            )}
          </>
        )}
        {view === "Reservations" && (
          <section className="table-wrap">
            <h2>Volunteer reservations</h2>
            <table>
              <thead>
                <tr>
                  <th>Item / pickup</th>
                  <th>Quantity</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {reservations
                  .filter((r) => own.some((p) => p.id === r.pickup_id))
                  .map((r) => (
                    <tr key={r.id}>
                      <td>
                        {r.item_name}
                        <small>{r.pickup_id.slice(-8)}</small>
                      </td>
                      <td>{r.quantity}</td>
                      <td>
                        <span className={"badge " + r.status}>{r.status}</span>
                      </td>
                      <td>
                        {r.status === "active" && (
                          <button
                            className="secondary"
                            disabled={busy}
                            onClick={() =>
                              action(
                                () => api(`/reservations/${r.id}/cancel`, {}),
                                "Reservation cancelled; stock released.",
                              )
                            }
                          >
                            Cancel
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
            {!reservations.some((r) =>
              own.some((p) => p.id === r.pickup_id),
            ) && <p>No reservations for this volunteer yet.</p>}
          </section>
        )}
        {view === "Pickups" && (
          <section className="table-wrap">
            <h2>Pickup records</h2>
            <table>
              <thead>
                <tr>
                  <th>Pickup ID</th>
                  <th>Status</th>
                  <th>Collected</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {own.map((p) => (
                  <tr key={p.id}>
                    <td className="mono">{p.id}</td>
                    <td>
                      <span className={"badge " + p.status}>{p.status}</span>
                    </td>
                    <td>
                      {p.fulfilled_at
                        ? new Date(p.fulfilled_at).toLocaleString()
                        : "—"}
                    </td>
                    <td>
                      {p.status === "open" && (
                        <button
                          disabled={
                            busy ||
                            !reservations.some(
                              (r) =>
                                r.pickup_id === p.id && r.status === "active",
                            )
                          }
                          onClick={() =>
                            action(
                              () => api(`/pickups/${p.id}/fulfill`, {}),
                              "Pickup collected.",
                            )
                          }
                        >
                          Mark collected
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!own.length && <p>Create a pickup to start reserving items.</p>}
          </section>
        )}
      </main>
      {showForm && (
        <div className="overlay">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="form-title"
          >
            <h2 id="form-title">
              {editing ? "Edit item" : "Add donated item"}
            </h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                action(async () => {
                  await api(
                    editing ? `/items/${editing.id}` : "/items",
                    {
                      name: f.get("name"),
                      category: f.get("category"),
                      condition: f.get("condition"),
                      on_hand: Number(f.get("on_hand")),
                    },
                    editing ? "PUT" : "POST",
                  );
                  setShowForm(false);
                }, "Item saved.");
              }}
            >
              <label>
                Item name
                <input
                  autoFocus
                  name="name"
                  required
                  maxLength={100}
                  defaultValue={editing?.name}
                />
              </label>
              <label>
                Category
                <input
                  name="category"
                  required
                  maxLength={60}
                  defaultValue={editing?.category}
                />
              </label>
              <label>
                Condition
                <select
                  name="condition"
                  defaultValue={editing?.condition || "good"}
                >
                  <option>new</option>
                  <option>good</option>
                  <option>fair</option>
                </select>
              </label>
              <label>
                Physical units on hand
                <input
                  name="on_hand"
                  type="number"
                  required
                  min={editing?.reserved || 0}
                  max="1000000"
                  defaultValue={editing?.on_hand || 0}
                />
              </label>
              <p>Include reserved units in the on-hand total.</p>
              <button disabled={busy}>Save item</button>
              <button
                type="button"
                className="link"
                onClick={() => setShowForm(false)}
              >
                Close
              </button>
              <p role="status">{message}</p>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
