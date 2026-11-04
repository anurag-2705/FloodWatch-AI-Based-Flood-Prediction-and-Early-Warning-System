import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer, Legend } from "recharts";

const API = import.meta.env.VITE_API || "http://localhost:8000/api";
const COLOR = { LOW: "#3fb27f", MEDIUM: "#e8b73a", HIGH: "#e5484d" };
const get = (p) => fetch(API + p).then((r) => r.json());
const post = (p, b) => fetch(API + p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
const Badge = ({ risk }) => <span className="badge" style={{ background: COLOR[risk] || "#8fa3bb" }}>{risk || "NO DATA"}</span>;

function Chart({ id }) {
  const [d, setD] = useState(null);
  useEffect(() => { get(`/forecast/${id}/`).then(setD); }, [id]);
  if (!d) return <p className="small">Loading…</p>;
  const rows = d.readings.map((r) => ({ t: r.date.slice(5), actual: Math.round(r.discharge) }));
  const last = d.predictions[d.predictions.length - 1];
  if (last) rows.push({ t: last.forecast_time.slice(5), forecast: Math.round(last.predicted_discharge) });
  return (
    <ResponsiveContainer width="100%" height={230}>
      <LineChart data={rows}>
        <XAxis dataKey="t" stroke="#8fa3bb" fontSize={11} minTickGap={30} />
        <YAxis stroke="#8fa3bb" fontSize={11} unit=" m³/s" domain={["auto", "auto"]} />
        <Tooltip contentStyle={{ background: "#0f1c2e", border: "1px solid #26405f" }} /><Legend />
        <ReferenceLine y={d.station.danger_level} stroke="#e5484d" strokeDasharray="4 4" label={{ value: "Flood threshold", fill: "#e5484d", fontSize: 11 }} />
        <Line dataKey="actual" name="Observed discharge" stroke="#5aa2ff" dot={false} />
        <Line dataKey="forecast" name="3-day forecast" stroke="#e8b73a" dot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function Replay({ id }) {
  const [events, setEvents] = useState(null); const [date, setDate] = useState(""); const [r, setR] = useState(null); const [err, setErr] = useState("");
  useEffect(() => { get(`/replay/events/${id}/`).then((j) => setEvents(j.events || [])).catch(() => setEvents([])); }, [id]);
  const run = async (d) => {
    if (!d) return; setDate(d); setErr("");
    const res = await fetch(`${API}/replay/${id}/?date=${d}`); const j = await res.json();
    if (res.ok) setR(j); else { setR(null); setErr(j.error || "Replay failed"); }
  };
  const rows = r ? r.series.map((x) => ({ t: x.date.slice(2), observed: Math.round(x.discharge), forecast: x.date === r.forecast_date ? Math.round(r.predicted_discharge) : undefined })) : [];
  const hit = (events || []).filter((e) => e.predicted !== "LOW").length;
  return (
    <section><h2>Replay past floods</h2>
      <p className="small">Pick a real past date. The model sees only data up to that day and forecasts 3 days ahead. Rain forecast is assumed perfect (actual rain used).</p>
      <div className="row"><input type="date" min="1984-02-01" max="2024-12-01" value={date} onChange={(e) => setDate(e.target.value)} /><button style={{ marginTop: 0 }} onClick={() => run(date)}>Replay this date</button></div>
      {err && <p className="small">{err}</p>}
      {r && <>
        <p>Predicted <Badge risk={r.predicted_risk} /> · Actual <Badge risk={r.actual_risk} /> · forecast {Math.round(r.predicted_discharge).toLocaleString()} vs actual {Math.round(r.actual_discharge).toLocaleString()} m³/s</p>
        <ResponsiveContainer width="100%" height={220}><LineChart data={rows}>
          <XAxis dataKey="t" stroke="#8fa3bb" fontSize={11} minTickGap={25} /><YAxis stroke="#8fa3bb" fontSize={11} />
          <Tooltip contentStyle={{ background: "#0f1c2e", border: "1px solid #26405f" }} /><Legend />
          <ReferenceLine y={r.threshold} stroke="#e5484d" strokeDasharray="4 4" />
          <ReferenceLine x={r.issue_date.slice(2)} stroke="#8fa3bb" label={{ value: "Forecast issued", fill: "#8fa3bb", fontSize: 11 }} />
          <Line dataKey="observed" name="Observed" stroke="#5aa2ff" dot={false} /><Line dataKey="forecast" name="Model forecast" stroke="#e8b73a" dot={{ r: 6 }} />
        </LineChart></ResponsiveContainer></>}
      {events && events.length > 0 && <>
        <p className="small" style={{ marginTop: 10 }}>Biggest past flood peaks. Model flagged MEDIUM/HIGH 3 days ahead for {hit} of {events.length}.</p>
        {events.map((e) => (
          <div key={e.peak_date} className="alert" style={{ borderColor: COLOR[e.actual] }}>
            Peak {e.peak_date} · {e.peak_discharge.toLocaleString()} m³/s · predicted <Badge risk={e.predicted} /> {e.unseen && <span className="small">(not in training data)</span>}
            <button style={{ marginTop: 4 }} onClick={() => run(e.issue_date)}>Replay forecast from {e.issue_date}</button>
          </div>))}</>}
    </section>
  );
}

function WhatIf() {
  const [f, setF] = useState({ discharge: 3000, rain_3d: 120, rain_next3: 0, danger: 8000 }); const [out, setOut] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const run = async () => setOut(await (await post("/predict/", f)).json());
  return (
    <section><h2>What-if simulator</h2>
      <div className="row"><label>River discharge (m³/s)<input type="number" value={f.discharge} onChange={set("discharge")} /></label>
        <label>Rain, last 3 days (mm)<input type="number" value={f.rain_3d} onChange={set("rain_3d")} /></label></div>
      <label>Forecast rain, next 3 days (mm)<input type="number" value={f.rain_next3} onChange={set("rain_next3")} /></label>
      <label>Flood threshold (m³/s)<input type="number" value={f.danger} onChange={set("danger")} /></label>
      <button onClick={run}>Predict risk</button>
      {out && <p>Risk <Badge risk={out.risk_level} /> · forecast {out.predicted_discharge} m³/s · high-risk probability {Math.round(out.probability * 100)}%</p>}
    </section>
  );
}

function Subscribe({ stations }) {
  const [f, setF] = useState({ name: "", email: "", phone: "", station: "", min_risk: "HIGH" }); const [msg, setMsg] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async () => {
    try {
      const r = await post("/subscribe/", { ...f, station: Number(f.station || stations[0]?.id) });
      setMsg(r.ok ? "Subscribed. You will be alerted for this station." : "Error: " + JSON.stringify(await r.json()));
    } catch (e) { setMsg("Cannot reach the API at " + API); }
  };
  return (
    <section><h2>Get alerts</h2>
      <label>Name<input value={f.name} onChange={set("name")} /></label>
      <div className="row"><label>Email<input type="email" value={f.email} onChange={set("email")} /></label>
        <label>Phone<input value={f.phone} onChange={set("phone")} /></label></div>
      <div className="row"><label>Station<select value={f.station} onChange={set("station")}>{stations.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
        <label>Alert from<select value={f.min_risk} onChange={set("min_risk")}><option value="MEDIUM">Medium risk</option><option value="HIGH">High risk</option></select></label></div>
      <button onClick={submit}>Subscribe</button><p className="small">{msg}</p>
    </section>
  );
}

export default function App() {
  const [stations, setStations] = useState([]); const [alerts, setAlerts] = useState([]); const [sel, setSel] = useState(null);
  useEffect(() => {
    const load = () => { get("/stations/").then((s) => { setStations(s); setSel((c) => c ?? s[0]?.id); }); get("/alerts/").then(setAlerts); };
    load(); const t = setInterval(load, 60000); return () => clearInterval(t);
  }, []);
  const cur = stations.find((s) => s.id === sel);
  return (<>
    <header><h1>FloodWatch</h1><span className="small">Model {cur?.latest?.model_version || "v1"} · data from ERA5 + GloFAS</span></header>
    <main>
      <div style={{ display: "grid", gap: 16 }}>
        <section><h2>Stations</h2>
          <MapContainer center={[24, 82]} zoom={5} className="map">
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap" />
            {stations.map((s) => (
              <CircleMarker key={s.id} center={[s.lat, s.lon]} radius={s.id === sel ? 14 : 10}
                pathOptions={{ color: COLOR[s.latest?.risk_level] || "#8fa3bb", fillOpacity: 0.7 }} eventHandlers={{ click: () => setSel(s.id) }}>
                <Popup>{s.name} ({s.river})<br />Risk: {s.latest?.risk_level || "no data"}</Popup>
              </CircleMarker>))}
          </MapContainer></section>
        <section><h2>{cur ? `${cur.name}, ${cur.river}` : "Select a station"} {cur && <Badge risk={cur.latest?.risk_level} />}</h2>
          {sel && <Chart id={sel} />}</section>
        {sel && <Replay id={sel} key={sel} />}
      </div>
      <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
        <section><h2>Active alerts</h2>
          {alerts.length === 0 && <p className="small">No alerts. All stations are below the warning threshold.</p>}
          {alerts.map((a) => <div key={a.id} className="alert" style={{ borderColor: COLOR[a.severity] }}><Badge risk={a.severity} /> {a.message}<div className="small">{new Date(a.sent_at).toLocaleString()}</div></div>)}
        </section>
        <WhatIf /><Subscribe stations={stations} />
      </div>
    </main></>);
}
