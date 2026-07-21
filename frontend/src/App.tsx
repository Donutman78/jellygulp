import { useEffect, useState } from "react";
import {
  Activity,
  CircleUserRound,
  Clapperboard,
  Clock3,
  Film,
  Gauge,
  Library,
  MonitorPlay,
  Pause,
  Play,
  Radio,
  Server,
  Tv,
  Volume2,
} from "lucide-react";

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

const number = new Intl.NumberFormat();

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

function methodClass(method: string): string {
  return method.toLowerCase().replace(/\s+/g, "-");

}

function StatCard({
  icon,
  label,
  value,
  detail,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <article className="stat-card">
      <div className="stat-icon">{icon}</div>
      <div>
        <p className="eyebrow">{label}</p>
        <p className="stat-value">{value}</p>
        {detail && <p className="muted">{detail}</p>}
      </div>
    </article>
  );
}

function SessionCard({ session }: { session: Session }) {
  const subtitle = session.series_name
    ? `${session.series_name}${session.season_name ? ` · ${session.season_name}` : ""}${
        session.episode_number ? ` · Episode ${session.episode_number}` : ""
      }`
    : session.title;

  const bitrate = formatBitrate(session.bitrate);

  return (
    <article className="session-card">
      <div className="poster">
        {session.image_url ? (
          <img src={session.image_url} alt="" />
        ) : (
          <Clapperboard size={38} />
        )}
      </div>

      <div className="session-content">
        <div className="session-heading">
          <div className="session-title-block">
            <p className="session-title">{session.title}</p>
            <p className="muted">{subtitle}</p>
          </div>

          <div className="badge-row">
            <span className={`pill ${methodClass(session.play_method)}`}>
              {session.play_method}
            </span>
            {session.resolution && (
              <span className="pill neutral">{session.resolution}</span>
            )}
            {session.is_hdr && (
              <span className="pill hdr">{session.video_range || "HDR"}</span>
            )}
          </div>
        </div>

        <div className="progress-track">
          <div
            className="progress-bar"
            style={{
              width: `${Math.max(0, Math.min(session.progress_percent, 100))}%`,
            }}
          />
        </div>

        <div className="session-progress-row">
          <span className="play-state">
            {session.is_paused ? <Pause size={13} /> : <Play size={13} />}
            {session.is_paused ? "Paused" : `${session.progress_percent}% watched`}
          </span>

          <span className="remaining">
            <Clock3 size={13} />
            {formatTime(session.remaining_seconds)}
          </span>
        </div>

        <div className="technical-grid">
          <span>
            <CircleUserRound size={14} />
            {session.user_name}
          </span>

          <span>
            <MonitorPlay size={14} />
            {session.device_name} · {session.client}
          </span>

          {(session.video_codec || bitrate) && (
            <span>
              <Gauge size={14} />
              {[session.video_codec?.toUpperCase(), bitrate]
                .filter(Boolean)
                .join(" · ")}
            </span>
          )}

          {session.audio_codec && (
            <span>
              <Volume2 size={14} />
              {session.audio_codec.toUpperCase()}
              {session.audio_channels
                ? ` · ${session.audio_channels} ch`
                : ""}
            </span>
          )}
        </div>

        {session.transcode_reasons.length > 0 && (
          <p className="transcode-note">
            Transcode reason: {session.transcode_reasons.join(", ")}
          </p>
        )}
      </div>
    </article>
  );
}

export default function App() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  async function load() {
    try {
      const response = await fetch("/api/dashboard");

      if (!response.ok) {
        throw new Error(`Dashboard request returned ${response.status}`);
      }

      setData(await response.json());
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 10_000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <main>
      <header className="topbar">
        <div className="brand">
          <div className="logo-mark">
            <Activity size={23} />
          </div>
          <div>
            <h1>JellyGulp</h1>
            <p>Media intelligence for Jellyfin</p>
          </div>
        </div>

        <div className="status">
          <span className={`status-dot ${error ? "offline" : ""}`} />
          {error ? "Connection issue" : "Jellyfin online"}
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">SERVER OVERVIEW</p>
          <h2>{data?.server.name || "Loading Jellyfin…"}</h2>
          <p className="hero-copy">
            {data
              ? `Jellyfin ${data.server.version} · ${data.server.operating_system}`
              : "Connecting to the JellyGulp backend."}
          </p>
        </div>

        <div className="updated">
          Updated {lastUpdated ? lastUpdated.toLocaleTimeString() : "—"}
        </div>
      </section>

      {error && (
        <section className="error-panel">
          <strong>JellyGulp could not load the dashboard.</strong>
          <span>{error}</span>
        </section>
      )}

      <section className="stats-grid">
        <StatCard
          icon={<Radio size={22} />}
          label="Active streams"
          value={data?.activity.active_streams ?? "—"}
          detail="Live right now"
        />
        <StatCard
          icon={<Film size={22} />}
          label="Movies"
          value={data ? number.format(data.counts.movies) : "—"}
          detail={`${data ? number.format(data.counts.episodes) : "—"} episodes`}
        />
        <StatCard
          icon={<Tv size={22} />}
          label="Series"
          value={data ? number.format(data.counts.series) : "—"}
          detail="Across all libraries"
        />
        <StatCard
          icon={<CircleUserRound size={22} />}
          label="Users"
          value={data?.users.total ?? "—"}
          detail={`${data?.users.disabled ?? "—"} disabled`}
        />
        <StatCard
          icon={<Library size={22} />}
          label="Play starts"
          value={data?.activity.play_starts_30d ?? "—"}
          detail="Recorded in 30 days"
        />
        <StatCard
          icon={<Server size={22} />}
          label="Events stored"
          value={data?.activity.recorded_events_30d ?? "—"}
          detail="Starts, pauses and stops"
        />
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">LIVE ACTIVITY</p>
            <h3>Currently watching</h3>
          </div>

          <span className="count-badge">{data?.sessions.length ?? 0}</span>
        </div>

        <div className="session-list">
          {data?.sessions.length ? (
            data.sessions.map((session) => (
              <SessionCard key={session.session_id} session={session} />
            ))
          ) : (
            <div className="empty-state">
              <Radio size={34} />
              <h4>No active streams</h4>
              <p>Start playing something in Jellyfin and it will appear here.</p>
            </div>
          )}
        </div>
      </section>

      <footer>JellyGulp v0.2 · Enhanced live sessions</footer>
    </main>
  );
}
