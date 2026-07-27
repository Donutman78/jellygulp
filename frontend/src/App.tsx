import { useEffect, useMemo, useState } from "react";
import {
  Clapperboard,
  Clock3,
  CircleUserRound,
  Film,
  Gauge as GaugeIcon,
  MonitorPlay,
  Pause,
  Play,
  Radio,
  Tv,
  Volume2,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Session = {
  session_id: string;
  user_name: string;
  client: string;
  device_name: string;
  title: string;
  series_name?: string;
  season_name?: string;
  episode_number?: number;
  progress_percent: number;
  remaining_seconds: number;
  is_paused: boolean;
  play_method: string;
  resolution?: string;
  is_hdr: boolean;
  video_range?: string;
  video_codec?: string;
  audio_codec?: string;
  audio_channels?: number | string;
  container?: string;
  bitrate?: number;
  transcode_reasons: string[];
  image_url?: string;
};

type Dashboard = {
  server: {
    name: string;
    version: string;
    operating_system: string;
  };
  counts: {
    movies: number;
    series: number;
    episodes: number;
    songs: number;
    albums: number;
  };
  users: {
    total: number;
    disabled: number;
  };
  activity: {
    active_streams: number;
    recorded_events_30d: number;
    play_starts_30d: number;
  };
  sessions: Session[];
};

type Health = {
  status: string;
  jellyfin_connected: boolean;
  database_connected: boolean;
};

type TeamScore = {
  state: "pre" | "in" | "post" | null;
  status_detail: string | null;
  start_time: string | null;
  cleveland_team: string | null;
  cleveland_score: string | null;
  cleveland_logo: string | null;
  cleveland_is_home: boolean;
  opponent_team: string | null;
  opponent_score: string | null;
  opponent_logo: string | null;
};

type SportsScores = {
  browns: TeamScore | null;
  cavaliers: TeamScore | null;
  guardians: TeamScore | null;
};

type SeerrItem = {
  id: number;
  type: string;
  title: string;
  poster_url: string | null;
  requested_by: string | null;
  requested_at: string | null;
};

type RecentItem = {
  id: string;
  title: string;
  subtitle: string | null;
  type: string;
  date_created: string | null;
  image_url: string | null;
};

type Analytics = {
  days: number;
  daily: { date: string; plays: number; transcodes: number; direct_plays: number }[];
  top_titles: { title: string; plays: number }[];
  top_users: { user_name: string; plays: number }[];
  summary: {
    total_plays: number;
    transcodes: number;
    direct_plays: number;
    unique_users: number;
  };
};

type HistoryEvent = {
  id: number;
  user_name: string | null;
  item_name: string | null;
  series_name: string | null;
  item_type: string | null;
  play_method: string | null;
  event_type: string;
  occurred_at: string;
};

const number = new Intl.NumberFormat();
const EVENT_LABELS: Record<string, string> = {
  started: "Play start",
  stopped: "Play stop",
  paused: "Paused",
  resumed: "Resumed",
};

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "—";
  }

  const rounded = Math.round(seconds);
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);

  if (hours > 0) {
    return `${hours}h ${minutes}m left`;
  }

  return `${Math.max(minutes, 1)}m left`;
}

function formatBitrate(value?: number): string | null {
  if (!value) {
    return null;
  }

  const mbps = value / 1_000_000;

  if (mbps >= 1) {
    return `${mbps.toFixed(mbps >= 10 ? 0 : 1)} Mbps`;
  }

  return `${Math.round(value / 1000)} Kbps`;
}

function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) {
    return "";
  }

  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function isTranscoding(method: string): boolean {
  return method.toLowerCase().includes("transcode");
}

function formatPlayMethod(method: string): string {
  const spaced = method.replace(/([a-z])([A-Z])/g, "$1 $2");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

function RadialGauge({
  value,
  max,
  size = 150,
  strokeWidth = 8,
  color,
  children,
}: {
  value: number;
  max: number;
  size?: number;
  strokeWidth?: number;
  color: string;
  children?: React.ReactNode;
}) {
  const radius = size / 2 - strokeWidth;
  const circumference = 2 * Math.PI * radius;
  const pct = max > 0 ? Math.max(0, Math.min(value / max, 1)) : 0;
  const offset = circumference * (1 - pct);
  const center = size / 2;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke="rgba(77,243,255,0.12)"
        strokeWidth={strokeWidth}
      />
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${center} ${center})`}
        style={{ filter: `drop-shadow(0 0 6px ${color})`, transition: "stroke-dashoffset 0.6s ease" }}
      />
      {children}
    </svg>
  );
}

function MiniGauge({ value, max, color, label }: { value: number; max: number; color: string; label: string }) {
  return (
    <div className="mini">
      <RadialGauge value={value} max={max} size={44} strokeWidth={5} color={color} />
      <p className="mini-label">{label}</p>
    </div>
  );
}

function StatTile({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="panel">
      <p className="stat-label">{label}</p>
      <p className="stat-val glow">{value}</p>
      {sub && <p className="stat-sub">{sub}</p>}
    </div>
  );
}

function SessionCard({ session }: { session: Session }) {
  const subtitle = session.series_name
    ? `${session.series_name}${session.season_name ? ` · ${session.season_name}` : ""}${
        session.episode_number ? ` · Episode ${session.episode_number}` : ""
      }`
    : null;

  const bitrate = formatBitrate(session.bitrate);
  const transcoding = isTranscoding(session.play_method);
  const posterSrc = session.image_url ? `${API_BASE}${session.image_url}` : null;

  return (
    <article className={`session${transcoding ? " warn" : ""}`}>
      <div className="poster">
        {posterSrc ? <img src={posterSrc} alt="" /> : <Clapperboard size={22} />}
      </div>

      <div className="session-body">
        <div className="session-top">
          <div>
            <p className="session-title">{session.title}</p>
            {subtitle && <p className="session-sub">{subtitle}</p>}
          </div>

          <div className="badge-row">
            <span className={`pill${transcoding ? " amber" : ""}`}>{formatPlayMethod(session.play_method)}</span>
            {session.resolution && <span className="pill violet">{session.resolution}</span>}
            {session.is_hdr && <span className="pill violet">{session.video_range || "HDR"}</span>}
          </div>
        </div>

        <div className="track">
          <div
            className={`bar${transcoding ? " warn" : ""}`}
            style={{ width: `${Math.max(0, Math.min(session.progress_percent, 100))}%` }}
          />
        </div>

        <div className="session-progress-row">
          <span className="play-state">
            {session.is_paused ? <Pause size={12} /> : <Play size={12} />}
            {session.is_paused ? "Paused" : `${session.progress_percent}% watched`}
          </span>
          <span className="remaining">
            <Clock3 size={12} />
            {formatTime(session.remaining_seconds)}
          </span>
        </div>

        <div className="meta">
          <span>
            <CircleUserRound size={13} />
            {session.user_name}
          </span>
          <span>
            <MonitorPlay size={13} />
            {session.device_name} · {session.client}
          </span>
          {(session.video_codec || bitrate) && (
            <span>
              <GaugeIcon size={13} />
              {[session.video_codec?.toUpperCase(), bitrate].filter(Boolean).join(" · ")}
            </span>
          )}
          {session.audio_codec && (
            <span>
              <Volume2 size={13} />
              {session.audio_codec.toUpperCase()}
              {session.audio_channels ? ` · ${session.audio_channels} ch` : ""}
            </span>
          )}
        </div>

        {session.transcode_reasons.length > 0 && (
          <p className="transcode-note">Transcode reason: {session.transcode_reasons.join(", ")}</p>
        )}
      </div>
    </article>
  );
}

function TeamCard({ label, game }: { label: string; game: TeamScore | null }) {
  if (!game) {
    return (
      <div className="team-card">
        <p className="eyebrow">{label}</p>
        <p className="team-empty">No game found</p>
      </div>
    );
  }

  const cleveland = Number(game.cleveland_score);
  const opponent = Number(game.opponent_score);
  const isFinal = game.state === "post";
  const clevelandWon = isFinal && !Number.isNaN(cleveland) && !Number.isNaN(opponent) && cleveland > opponent;
  const clevelandLost = isFinal && !Number.isNaN(cleveland) && !Number.isNaN(opponent) && cleveland < opponent;

  return (
    <div className="team-card">
      <div className="team-card-top">
        <p className="eyebrow">{label}</p>
        {game.state === "in" && (
          <span className="pill amber">
            <span className="dot" style={{ width: 6, height: 6, marginRight: 4 }} />
            Live
          </span>
        )}
        {isFinal && (
          <span className={`pill${clevelandWon ? "" : clevelandLost ? " amber" : ""}`}>Final</span>
        )}
      </div>

      {game.state === "pre" ? (
        <>
          <p className="team-matchup">vs {game.opponent_team}</p>
          <p className="team-empty">
            {game.start_time
              ? new Date(game.start_time).toLocaleString(undefined, {
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                })
              : game.status_detail}
          </p>
        </>
      ) : (
        <>
          <div className="team-score-row">
            <span className={clevelandWon ? "glow" : undefined}>{game.cleveland_score ?? "—"}</span>
            <span className="team-vs">{game.cleveland_is_home ? "vs" : "@"}</span>
            <span className={clevelandLost ? "glow" : undefined}>{game.opponent_score ?? "—"}</span>
          </div>
          <p className="team-matchup">{game.opponent_team}</p>
          {game.status_detail && <p className="team-empty">{game.status_detail}</p>}
        </>
      )}
    </div>
  );
}

function SideBanner({
  label,
  items,
  direction,
  onOpen,
}: {
  label: string;
  items: SeerrItem[];
  direction: "left" | "right";
  onOpen: () => void;
}) {
  const loop = items.length > 0 ? [...items, ...items] : [];
  const duration = Math.max(20, items.length * 7);

  return (
    <button
      type="button"
      className={`side-banner ${direction}`}
      onClick={onOpen}
      aria-label={`Open ${label.toLowerCase()}`}
    >
      <span className="side-banner-label">{label}</span>
      <div className="side-banner-scroll">
        {items.length === 0 ? (
          <p className="side-banner-empty">Nothing here yet</p>
        ) : (
          <div className="side-banner-track" style={{ animationDuration: `${duration}s` }}>
            {loop.map((item, i) => (
              <div className="side-banner-item" key={`${item.id}-${i}`}>
                <div className="side-banner-poster">
                  {item.poster_url ? <img src={item.poster_url} alt="" /> : <Clapperboard size={16} />}
                </div>
                <span className="side-banner-title">{item.title}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </button>
  );
}

function RequestCard({ item }: { item: SeerrItem }) {
  return (
    <div className="recent-card">
      <div className="recent-poster">
        {item.poster_url ? <img src={item.poster_url} alt="" /> : <Clapperboard size={20} />}
      </div>
      <p className="recent-title">{item.title}</p>
      {item.requested_by && <p className="recent-sub">by {item.requested_by}</p>}
      {item.requested_at && <p className="recent-sub">{formatRelativeTime(item.requested_at)}</p>}
    </div>
  );
}

function RequestsView({
  wishlist,
  comingSoon,
  error,
}: {
  wishlist: SeerrItem[];
  comingSoon: SeerrItem[];
  error: string | null;
}) {
  if (error) {
    return (
      <div className="panel">
        <p className="empty-note">Requests unavailable: {error}. Redeploy the backend to enable this view.</p>
      </div>
    );
  }

  return (
    <>
      <div className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Awaiting approval</p>
            <h3>Wishlist</h3>
          </div>
          <span className="count-badge">{wishlist.length}</span>
        </div>
        {wishlist.length === 0 ? (
          <p className="empty-note">Nothing pending right now.</p>
        ) : (
          <div className="request-grid">
            {wishlist.map((item) => (
              <RequestCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Approved, awaiting storage</p>
            <h3>Coming soon</h3>
          </div>
          <span className="count-badge">{comingSoon.length}</span>
        </div>
        {comingSoon.length === 0 ? (
          <p className="empty-note">Nothing queued right now.</p>
        ) : (
          <div className="request-grid">
            {comingSoon.map((item) => (
              <RequestCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function RecentlyAddedRow({ items }: { items: RecentItem[] }) {
  return (
    <div className="panel recent-panel">
      <p className="eyebrow">Library</p>
      <h3 style={{ margin: "2px 0 10px", fontSize: 14, textTransform: "uppercase", letterSpacing: "0.08em" }}>
        Recently added
      </h3>
      {items.length === 0 ? (
        <p className="empty-note">Nothing new indexed yet.</p>
      ) : (
        <div className="recent-strip">
          {items.map((item) => (
            <div className="recent-card" key={item.id}>
              <div className="recent-poster">
                {item.image_url ? (
                  <img src={`${API_BASE}${item.image_url}`} alt="" />
                ) : (
                  <Clapperboard size={20} />
                )}
              </div>
              <p className="recent-title">{item.title}</p>
              {item.subtitle && <p className="recent-sub">{item.subtitle}</p>}
              {item.date_created && <p className="recent-sub">{formatRelativeTime(item.date_created)}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Leaderboard({ items }: { items: { name: string; plays: number }[] }) {
  if (items.length === 0) {
    return <p className="empty-note">No plays recorded in this window yet.</p>;
  }

  const max = Math.max(...items.map((i) => i.plays), 1);

  return (
    <div>
      {items.map((item, i) => (
        <div key={item.name + i}>
          <div className="leader-row">
            <span className="leader-rank">{i + 1}</span>
            <span className="leader-name">{item.name}</span>
            <span className="leader-count">{item.plays}</span>
          </div>
          <div className="leader-track">
            <div className="leader-fill" style={{ width: `${(item.plays / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const direct = payload.find((p: any) => p.dataKey === "direct_plays")?.value ?? 0;
  const transcode = payload.find((p: any) => p.dataKey === "transcodes")?.value ?? 0;

  return (
    <div className="panel" style={{ padding: "8px 12px", fontSize: 11 }}>
      <p className="eyebrow" style={{ marginBottom: 4 }}>{label}</p>
      <p style={{ margin: 0, color: "#4df3ff" }}>Direct: {direct}</p>
      <p style={{ margin: 0, color: "#ffb454" }}>Transcode: {transcode}</p>
    </div>
  );
}

function shortDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function AnalyticsView({ analytics, error }: { analytics: Analytics | null; error: string | null }) {
  if (!analytics) {
    return (
      <div className="panel">
        <p className="empty-note">
          {error ? `Analytics unavailable: ${error}. Redeploy the backend to enable this view.` : "Loading analytics…"}
        </p>
      </div>
    );
  }

  const { summary, daily, top_titles, top_users } = analytics;
  const transcodePct = summary.total_plays
    ? Math.round((summary.transcodes / summary.total_plays) * 100)
    : 0;

  return (
    <>
      <div className="stats">
        <StatTile label={`Plays (${analytics.days}d)`} value={number.format(summary.total_plays)} />
        <StatTile
          label="Transcode ratio"
          value={`${transcodePct}%`}
          sub={`${number.format(summary.transcodes)} of ${number.format(summary.total_plays)}`}
        />
        <StatTile label="Unique viewers" value={summary.unique_users} />
      </div>

      <div className="analytics-grid">
        <div className="panel">
          <p className="eyebrow">Plays per day</p>
          <h3 style={{ margin: "2px 0 0", fontSize: 14, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Direct play vs transcode
          </h3>
          {daily.length === 0 ? (
            <p className="empty-note">No playback history recorded yet.</p>
          ) : (
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={daily} margin={{ top: 16, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke="rgba(77,243,255,0.12)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={shortDate}
                    stroke="#0f7a8c"
                    fontSize={10}
                    tickLine={false}
                  />
                  <YAxis stroke="#0f7a8c" fontSize={10} tickLine={false} allowDecimals={false} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(77,243,255,0.06)" }} />
                  <Bar dataKey="direct_plays" stackId="a" fill="#4df3ff" />
                  <Bar dataKey="transcodes" stackId="a" fill="#ffb454" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="leaderboards">
          <div className="panel">
            <p className="eyebrow">Most watched</p>
            <h3 style={{ margin: "2px 0 10px", fontSize: 14, textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Top titles
            </h3>
            <Leaderboard items={top_titles.map((t) => ({ name: t.title, plays: t.plays }))} />
          </div>

          <div className="panel">
            <p className="eyebrow">Most active</p>
            <h3 style={{ margin: "2px 0 10px", fontSize: 14, textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Top viewers
            </h3>
            <Leaderboard items={top_users.map((u) => ({ name: u.user_name, plays: u.plays }))} />
          </div>
        </div>
      </div>
    </>
  );
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export default function App() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [history, setHistory] = useState<HistoryEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"live" | "analytics" | "requests">("live");
  const [portal, setPortal] = useState<"left" | "right" | null>(null);

  function openRequests(direction: "left" | "right") {
    setPortal(direction);
    window.setTimeout(() => {
      setView("requests");
      setPortal(null);
    }, 520);
  }
  const [wishlist, setWishlist] = useState<SeerrItem[]>([]);
  const [comingSoon, setComingSoon] = useState<SeerrItem[]>([]);
  const [requestsError, setRequestsError] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [sports, setSports] = useState<SportsScores | null>(null);
  const [recentItems, setRecentItems] = useState<RecentItem[]>([]);

  async function load() {
    try {
      const [dashRes, healthRes, historyRes] = await Promise.all([
        fetch(`${API_BASE}/api/dashboard`),
        fetch(`${API_BASE}/api/health`),
        fetch(`${API_BASE}/api/history/recent?limit=20`),
      ]);

      if (!dashRes.ok) {
        throw new Error(`Dashboard request returned ${dashRes.status}`);
      }

      setData(await dashRes.json());
      setError(null);

      if (healthRes.ok) {
        setHealth(await healthRes.json());
      }
      if (historyRes.ok) {
        setHistory(await historyRes.json());
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 10_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (view !== "analytics") return;

    let cancelled = false;
    async function loadAnalytics() {
      try {
        const res = await fetch(`${API_BASE}/api/analytics?days=30`);
        if (cancelled) return;
        if (res.ok) {
          setAnalytics(await res.json());
          setAnalyticsError(null);
        } else {
          setAnalyticsError(`Analytics request returned ${res.status}`);
        }
      } catch (err) {
        if (!cancelled) {
          setAnalyticsError(err instanceof Error ? err.message : "Unknown error");
        }
      }
    }

    loadAnalytics();
    const timer = window.setInterval(loadAnalytics, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [view]);

  useEffect(() => {
    let cancelled = false;
    async function loadSports() {
      try {
        const res = await fetch(`${API_BASE}/api/sports/cleveland`);
        if (res.ok && !cancelled) {
          setSports(await res.json());
        }
      } catch {
        // leave last known scores in place on transient failure
      }
    }

    loadSports();
    const timer = window.setInterval(loadSports, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadRecent() {
      try {
        const res = await fetch(`${API_BASE}/api/recently-added?limit=16`);
        if (res.ok && !cancelled) {
          setRecentItems(await res.json());
        }
      } catch {
        // leave last known items in place on transient failure
      }
    }

    loadRecent();
    const timer = window.setInterval(loadRecent, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadRequests() {
      try {
        const [wishRes, soonRes] = await Promise.all([
          fetch(`${API_BASE}/api/seerr/wishlist`),
          fetch(`${API_BASE}/api/seerr/coming-soon`),
        ]);
        if (cancelled) return;
        if (wishRes.ok && soonRes.ok) {
          setWishlist(await wishRes.json());
          setComingSoon(await soonRes.json());
          setRequestsError(null);
        } else {
          setRequestsError(`Request returned ${wishRes.status}/${soonRes.status}`);
        }
      } catch (err) {
        if (!cancelled) {
          setRequestsError(err instanceof Error ? err.message : "Unknown error");
        }
      }
    }

    loadRequests();
    const timer = window.setInterval(loadRequests, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const sessions = data?.sessions ?? [];

  const transcodeCount = useMemo(
    () => sessions.filter((s) => isTranscoding(s.play_method)).length,
    [sessions],
  );

  const transcodePct = sessions.length ? (transcodeCount / sessions.length) * 100 : 0;

  const aggregateBitrateMbps = useMemo(
    () => sessions.reduce((sum, s) => sum + (s.bitrate ?? 0), 0) / 1_000_000,
    [sessions],
  );

  const activeUserCount = useMemo(
    () => new Set(sessions.map((s) => s.user_name)).size,
    [sessions],
  );

  const streamGaugeMax = Math.max(data?.users.total ?? 1, sessions.length, 1);

  return (
    <main>
      <div className="sweep" />

      <SideBanner label="Wishlist" items={wishlist} direction="left" onOpen={() => openRequests("left")} />
      <SideBanner label="Coming soon" items={comingSoon} direction="right" onOpen={() => openRequests("right")} />

      {portal && <div className={`portal-flash ${portal}`} />}

      <div className="content">
        <header className="topbar">
          <div className="brand">
            <div className="ring-badge">
              <div className="r1" />
              <div className="r2" />
            </div>
            <div>
              <h1 className="glow">JellyGulp</h1>
              <p>{data ? `${data.server.name} · Jellyfin ${data.server.version}` : "Media intelligence"}</p>
            </div>
          </div>
          <div className="tabs">
            <button
              type="button"
              className={`tab-btn${view === "live" ? " active" : ""}`}
              onClick={() => setView("live")}
            >
              Live
            </button>
            <button
              type="button"
              className={`tab-btn${view === "analytics" ? " active" : ""}`}
              onClick={() => setView("analytics")}
            >
              Analytics
            </button>
            <button
              type="button"
              className={`tab-btn${view === "requests" ? " active" : ""}`}
              onClick={() => setView("requests")}
            >
              Requests
            </button>
          </div>

          <div className="status">
            <span className={`dot${error ? " offline" : ""}`} />
            {error ? "Connection issue" : "Jellyfin link stable"}
          </div>
        </header>

        <div className={`ticker-wrap${history.length === 0 ? " idle" : ""}`}>
          {history.length === 0 ? (
            <span>AWAITING ACTIVITY…</span>
          ) : (
            <div
              className="ticker"
              style={{ animationDuration: `${Math.max(35, history.length * 9)}s` }}
            >
              {[...history, ...history].map((event, i) => (
                <span key={`${event.id}-${i}`} className={event.play_method && isTranscoding(event.play_method) ? "hot" : undefined}>
                  {(EVENT_LABELS[event.event_type] ?? event.event_type).toUpperCase()} · {event.user_name ?? "Unknown"} ·{" "}
                  {event.series_name ? `${event.series_name} — ${event.item_name}` : event.item_name} · {formatRelativeTime(event.occurred_at)}
                </span>
              ))}
            </div>
          )}
        </div>

        {error && (
          <section className="error-panel">
            <strong>JellyGulp could not reach the backend.</strong>
            <span>{error}</span>
          </section>
        )}

        {view === "live" && (
          <div className="sports-row">
            <TeamCard label="Browns" game={sports?.browns ?? null} />
            <TeamCard label="Cavaliers" game={sports?.cavaliers ?? null} />
            <TeamCard label="Guardians" game={sports?.guardians ?? null} />
          </div>
        )}

        {view === "analytics" ? (
          <AnalyticsView analytics={analytics} error={analyticsError} />
        ) : view === "requests" ? (
          <RequestsView wishlist={wishlist} comingSoon={comingSoon} error={requestsError} />
        ) : (
        <div className="grid">
          <div className="panel gauge-wrap">
            <p className="eyebrow">Live streams</p>
            <RadialGauge value={sessions.length} max={streamGaugeMax} color="#4df3ff">
              <text x="50%" y="46%" textAnchor="middle" fill="#4df3ff" fontSize="26" fontFamily="Consolas, monospace">
                {sessions.length}
              </text>
              <text x="50%" y="60%" textAnchor="middle" fill="#0f7a8c" fontSize="10" fontFamily="Consolas, monospace">
                STREAMS
              </text>
            </RadialGauge>
            <p className="gauge-caption">
              {activeUserCount} of {data?.users.total ?? "—"} users online
            </p>
            <div className="mini-row">
              <MiniGauge value={transcodePct} max={100} color="#ffb454" label={`Transcode ${Math.round(transcodePct)}%`} />
              <MiniGauge
                value={aggregateBitrateMbps}
                max={200}
                color="#b98bff"
                label={`${aggregateBitrateMbps >= 10 ? Math.round(aggregateBitrateMbps) : aggregateBitrateMbps.toFixed(1)} Mbps`}
              />
            </div>
          </div>

          <div>
            <div className="stats">
              <StatTile
                label="Movies"
                value={data ? number.format(data.counts.movies) : "—"}
                sub="Across movie libraries"
              />
              <StatTile
                label="Series"
                value={data ? number.format(data.counts.series) : "—"}
                sub={`${data ? number.format(data.counts.episodes) : "—"} episodes`}
              />
              <StatTile
                label="Users"
                value={data?.users.total ?? "—"}
                sub={`${data?.users.disabled ?? "—"} disabled`}
              />
            </div>

            <div className="panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Live activity</p>
                  <h3>Currently watching</h3>
                </div>
                <span className="count-badge">{sessions.length}</span>
              </div>

              <div className="sessions">
                {sessions.length ? (
                  sessions.map((session) => <SessionCard key={session.session_id} session={session} />)
                ) : (
                  <div className="empty-state">
                    <Radio size={28} />
                    <h4>No active streams</h4>
                    <p>Start playing something in Jellyfin and it will appear here.</p>
                  </div>
                )}
              </div>

              <div className="diag">
                <div className={`diag-item${health?.jellyfin_connected === false ? " down" : ""}`}>
                  <span className="d" />
                  Jellyfin API
                </div>
                <div className={`diag-item${health?.database_connected === false ? " down" : ""}`}>
                  <span className="d" />
                  Database
                </div>
                <div className={`diag-item${error ? " down" : ""}`}>
                  <span className="d" />
                  Dashboard feed
                </div>
              </div>
            </div>
          </div>
        </div>
        )}

        {view === "live" && <RecentlyAddedRow items={recentItems} />}

        <footer>
          JellyGulp · {data ? `${number.format(data.activity.play_starts_30d)} plays in 30d` : "Connecting…"}
        </footer>
      </div>
    </main>
  );
}
