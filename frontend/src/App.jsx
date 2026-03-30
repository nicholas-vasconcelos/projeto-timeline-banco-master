import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, Brush, ReferenceLine, Cell
} from 'recharts';

// ── Constants ────────────────────────────────────────────────────────────────
const CATEGORY_LABELS = {
  market:     { en: 'Market Move',  pt: 'Mercado'     },
  regulatory: { en: 'Regulatory',   pt: 'Regulatório' },
  legal:      { en: 'Legal',        pt: 'Jurídico'    },
  governance: { en: 'Governance',   pt: 'Governança'  },
  arrest:     { en: 'Arrest',       pt: 'Prisão'      },
  fraud:      { en: 'Fraud',        pt: 'Fraude'      },
};

const SENTIMENT_META = {
  bullish: { en: 'Bullish', pt: 'Altista',  light: '#dcfce7', dark: '#14532d', text: '#15803d' },
  bearish: { en: 'Bearish', pt: 'Baixista', light: '#fee2e2', dark: '#450a0a', text: '#dc2626' },
  neutral: { en: 'Neutral', pt: 'Neutro',   light: '#f1f5f9', dark: '#1e293b', text: '#64748b' },
  crisis:  { en: 'Crisis',  pt: 'Crise',    light: '#ede9fe', dark: '#2e1065', text: '#7c3aed' },
};

const CAT_COLOR = {
  market:     '#64748b',
  regulatory: '#2563eb',
  legal:      '#7c3aed',
  governance: '#b45309',
  arrest:     '#dc2626',
  fraud:      '#ea580c',
};

const LINE_OPTIONS = [
  { key: 'Close',  label: { en: 'BSLI4 Close',    pt: 'Fechamento BSLI4'   }, color: '#0f172a', required: true },
  { key: 'SMA_7',  label: { en: '7-day SMA',      pt: 'Média móvel 7d'     }, color: '#f59e0b' },
  { key: 'SMA_30', label: { en: '30-day SMA',     pt: 'Média móvel 30d'    }, color: '#10b981' },
];

const LINE_VISIBILITY_DEFAULTS = LINE_OPTIONS.reduce((acc, option) => {
  if (!option.required) acc[option.key] = true;
  return acc;
}, {});

// ── Theme tokens ─────────────────────────────────────────────────────────────
const T = {
  light: {
    bg:          'bg-slate-50',
    surface:     'bg-white',
    surfaceHov:  'hover:bg-slate-50',
    border:      'border-slate-200',
    borderDiv:   'divide-slate-100',
    text:        'text-slate-900',
    textMuted:   'text-slate-500',
    textFaint:   'text-slate-400',
    gridStroke:  '#f1f5f9',
    axisColor:   '#94a3b8',
    brushFill:   '#f8fafc',
    brushStroke: '#e2e8f0',
    inputBg:     'bg-white',
    tooltipBg:   '#ffffff',
    tooltipBorder:'#e2e8f0',
    tableHead:   'bg-slate-50',
    activeRow:   'bg-blue-50',
    toggleActive:'bg-blue-600 text-white',
    toggleIdle:  'text-slate-600 hover:bg-slate-100',
    statBg:      'bg-white',
    panelBg:     'bg-white',
    closeBtn:    'text-slate-400 hover:text-slate-600 hover:bg-slate-100',
  },
  dark: {
    bg:          'bg-slate-950',
    surface:     'bg-slate-900',
    surfaceHov:  'hover:bg-slate-800',
    border:      'border-slate-700',
    borderDiv:   'divide-slate-800',
    text:        'text-slate-100',
    textMuted:   'text-slate-400',
    textFaint:   'text-slate-500',
    gridStroke:  '#1e293b',
    axisColor:   '#475569',
    brushFill:   '#0f172a',
    brushStroke: '#334155',
    inputBg:     'bg-slate-800',
    tooltipBg:   '#1e293b',
    tooltipBorder:'#334155',
    tableHead:   'bg-slate-800',
    activeRow:   'bg-slate-700',
    toggleActive:'bg-blue-500 text-white',
    toggleIdle:  'text-slate-300 hover:bg-slate-700',
    statBg:      'bg-slate-800',
    panelBg:     'bg-slate-800',
    closeBtn:    'text-slate-400 hover:text-slate-200 hover:bg-slate-700',
  }
};

// ── Custom event dot ──────────────────────────────────────────────────────────
const EventDot = ({ cx, cy, payload, events, onHover, onClickDot, activeDate, lockedDate }) => {
  const ev = events.find(e => e.date === payload?.Date);
  if (!ev || cx == null || cy == null) return null;
  const isActive = activeDate === ev.date;
  const isLocked = lockedDate === ev.date;
  const color = CAT_COLOR[ev.category] || '#64748b';
  return (
    <g
      style={{ cursor: 'pointer' }}
      onMouseEnter={() => onHover(ev)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onClickDot(ev)}
    >
      <circle cx={cx} cy={cy} r={isActive || isLocked ? 12 : 8}
        fill="white" stroke={color} strokeWidth={isLocked ? 3 : isActive ? 2.5 : 2} />
      <circle cx={cx} cy={cy} r={isActive || isLocked ? 6 : 4} fill={color} />
      {isLocked && (
        <circle cx={cx} cy={cy} r={16}
          fill="none" stroke={color} strokeWidth={1.5} strokeDasharray="3 2" opacity={0.5} />
      )}
    </g>
  );
};

// ── Chart tooltip ─────────────────────────────────────────────────────────────
const ChartTooltip = ({ active, payload, label, dark }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  const bg = dark ? '#1e293b' : '#ffffff';
  const border = dark ? '#334155' : '#e2e8f0';
  const textMain = dark ? '#f1f5f9' : '#0f172a';
  const textMuted = dark ? '#94a3b8' : '#64748b';
  return (
    <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 12,
                  boxShadow: '0 4px 16px rgba(0,0,0,0.15)', padding: '10px 14px',
                  fontSize: 12, minWidth: 160 }}>
      <div style={{ fontWeight: 600, color: textMain, marginBottom: 8, fontFamily: 'monospace' }}>{label}</div>
      {payload.filter(p => p.dataKey !== 'Volume').map((p, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginBottom: 4 }}>
          <span style={{ color: p.color }}>{p.name}</span>
          <span style={{ fontFamily: 'monospace', fontWeight: 600, color: textMain }}>
            R$ {Number(p.value).toFixed(2)}
          </span>
        </div>
      ))}
      {d?.Volume > 0 && (
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16,
                      borderTop: `1px solid ${border}`, marginTop: 6, paddingTop: 6 }}>
          <span style={{ color: textMuted }}>Volume</span>
          <span style={{ fontFamily: 'monospace', color: textMuted }}>
            {d.Volume.toLocaleString('pt-BR')}
          </span>
        </div>
      )}
    </div>
  );
};

// ── Event detail panel ────────────────────────────────────────────────────────
const EventPanel = ({ event, lang, locked, onDismiss, dark }) => {
  const t = T[dark ? 'dark' : 'light'];
  if (!event) return (
    <div className={`flex items-center justify-center py-8 ${t.textFaint} text-sm italic`}>
      {lang === 'en'
        ? 'Click or hover a marker on the chart to see event details'
        : 'Clique ou passe o cursor sobre um marcador no gráfico'}
    </div>
  );

  const sent  = SENTIMENT_META[event.sentiment];
  const catLbl = CATEGORY_LABELS[event.category];
  const sentBg = dark ? sent.dark : sent.light;

  return (
    <div className="flex flex-col gap-3">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs" style={{ color: dark ? '#64748b' : '#94a3b8' }}>
            {event.date}
          </span>
          <span className="text-xs px-2.5 py-0.5 rounded-full font-medium"
            style={{ background: CAT_COLOR[event.category] + (dark ? '30' : '15'),
                     color: CAT_COLOR[event.category] }}>
            {catLbl?.[lang] || event.category}
          </span>
          <span className="text-xs px-2.5 py-0.5 rounded-full font-medium"
            style={{ background: sentBg, color: sent.text }}>
            {sent[lang]}
          </span>
          {locked && (
            <span className="text-xs px-2 py-0.5 rounded-full font-medium border"
              style={{ borderColor: CAT_COLOR[event.category],
                       color: CAT_COLOR[event.category] }}>
              {lang === 'en' ? 'Pinned' : 'Fixado'}
            </span>
          )}
        </div>
        {locked && (
          <button onClick={onDismiss}
            className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-sm transition-colors ${t.closeBtn}`}
            title={lang === 'en' ? 'Dismiss' : 'Fechar'}>
            ×
          </button>
        )}
      </div>

      {/* Title */}
      <h3 className={`text-base font-semibold leading-snug ${t.text}`}>
        {event[`title_${lang}`] || event.title_en}
      </h3>

      {/* Description */}
      <p className={`text-sm leading-relaxed ${t.textMuted}`}>
        {event[`description_${lang}`] || event.description_en}
      </p>

      {/* Price chips */}
      {(event.bsli4_change_pct != null || event.price_bsli4 != null) && (
        <div className="flex flex-wrap gap-2 pt-2 border-t" style={{ borderColor: dark ? '#334155' : '#f1f5f9' }}>
          {event.price_bsli4 != null && (
            <div className={`rounded-lg px-3 py-2 ${t.statBg}`} style={{ border: `1px solid ${dark ? '#334155' : '#e2e8f0'}` }}>
              <div className={`text-xs mb-0.5 ${t.textFaint}`}>
                {lang === 'en' ? 'Close' : 'Fechamento'}
              </div>
              <div className={`text-sm font-semibold font-mono ${t.text}`}>
                R$ {Number(event.price_bsli4).toFixed(2)}
              </div>
            </div>
          )}
          {event.bsli4_change_pct != null && (
            <div className="rounded-lg px-3 py-2"
              style={{ background: event.bsli4_change_pct > 0
                ? (dark ? '#14532d' : '#dcfce7')
                : (dark ? '#450a0a' : '#fee2e2'),
                border: `1px solid ${event.bsli4_change_pct > 0
                  ? (dark ? '#166534' : '#bbf7d0')
                  : (dark ? '#7f1d1d' : '#fecaca')}` }}>
              <div className="text-xs mb-0.5" style={{ color: dark ? '#6b7280' : '#94a3b8' }}>BSLI4</div>
              <div className="text-sm font-semibold font-mono"
                style={{ color: event.bsli4_change_pct > 0 ? '#16a34a' : '#dc2626' }}>
                {event.bsli4_change_pct > 0 ? '+' : ''}{event.bsli4_change_pct.toFixed(2)}%
              </div>
            </div>
          )}
          {event.bsli3_change_pct != null && (
            <div className="rounded-lg px-3 py-2"
              style={{ background: event.bsli3_change_pct > 0
                ? (dark ? '#14532d' : '#dcfce7')
                : (dark ? '#450a0a' : '#fee2e2'),
                border: `1px solid ${event.bsli3_change_pct > 0
                  ? (dark ? '#166534' : '#bbf7d0')
                  : (dark ? '#7f1d1d' : '#fecaca')}` }}>
              <div className="text-xs mb-0.5" style={{ color: dark ? '#6b7280' : '#94a3b8' }}>BSLI3</div>
              <div className="text-sm font-semibold font-mono"
                style={{ color: event.bsli3_change_pct > 0 ? '#16a34a' : '#dc2626' }}>
                {event.bsli3_change_pct > 0 ? '+' : ''}{event.bsli3_change_pct.toFixed(2)}%
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [marketData,   setMarketData]   = useState([]);
  const [events,       setEvents]       = useState([]);
  const [hoverEvent,   setHoverEvent]   = useState(null);   // transient hover
  const [lockedEvent,  setLockedEvent]  = useState(null);   // click-locked
  const [lang,         setLang]         = useState('en');
  const [filter,       setFilter]       = useState('all');
  const [dark,         setDark]         = useState(false);
  const [tableOpen,    setTableOpen]    = useState(false);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState(null);
  const [lineVisibility, setLineVisibility] = useState(() => ({ ...LINE_VISIBILITY_DEFAULTS }));

  const t = T[dark ? 'dark' : 'light'];

  // Active event = locked if exists, else hovered
  const activeEvent = lockedEvent || hoverEvent;
  const activeDate  = activeEvent?.date || null;

  useEffect(() => {
    (async () => {
      try {
        const [mktRes, evtRes] = await Promise.all([
          fetch('http://127.0.0.1:8000/api/market-data/'),
          fetch('http://127.0.0.1:8000/api/events/'),
        ]);
        if (!mktRes.ok) throw new Error(`Market data API error ${mktRes.status}`);
        if (!evtRes.ok) throw new Error(`Events API error ${evtRes.status}`);
        const mkt = await mktRes.json();
        const evt = await evtRes.json();
        if (!Array.isArray(mkt)) throw new Error('Market data malformed');
        setMarketData(mkt);
        setEvents(Array.isArray(evt) ? evt : (evt.events || []));
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleHover      = useCallback(ev => { if (!lockedEvent) setHoverEvent(ev); }, [lockedEvent]);
  const handleClickDot   = useCallback(ev => {
    setLockedEvent(prev => prev?.date === ev.date ? null : ev);
    setHoverEvent(null);
  }, []);
  const handleDismiss    = useCallback(() => { setLockedEvent(null); setHoverEvent(null); }, []);
  const handleRowHover   = useCallback(ev => { if (!lockedEvent) setHoverEvent(ev); }, [lockedEvent]);
  const handleRowClick   = useCallback(ev => {
    setLockedEvent(prev => prev?.date === ev.date ? null : ev);
    setHoverEvent(null);
  }, []);
  const handleRowLeave   = useCallback(() => { if (!lockedEvent) setHoverEvent(null); }, [lockedEvent]);
  const toggleLineVisibility = useCallback(key => {
    setLineVisibility(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const visibleEvents = filter === 'all' ? events : events.filter(e => e.category === filter);
  const eventDates    = new Set(visibleEvents.map(e => e.date));
  const categories    = ['all', ...Array.from(new Set(events.map(e => e.category)))];
  const volColor      = entry => (!entry.Open || !entry.Close) ? (dark ? '#334155' : '#cbd5e1')
                               : entry.Close >= entry.Open ? '#22c55e' : '#ef4444';

  if (loading) return (
    <div className={`flex items-center justify-center min-h-screen ${dark ? 'bg-slate-950' : 'bg-slate-50'}`}>
      <span className={`text-sm animate-pulse ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
        {lang === 'en' ? 'Loading timeline…' : 'Carregando…'}
      </span>
    </div>
  );

  if (error) return (
    <div className={`flex items-center justify-center min-h-screen p-6 ${dark ? 'bg-slate-950' : 'bg-slate-50'}`}>
      <div className="bg-red-950 border-l-4 border-red-500 rounded-lg p-6 max-w-xl w-full">
        <h2 className="text-lg font-bold text-red-400 mb-2">Connection Error</h2>
        <p className="text-sm text-red-300 mb-3">{error}</p>
        <p className="text-xs text-red-500">
          Ensure Django is running on port 8000 with <code>/api/market-data/</code> and <code>/api/events/</code> live.
        </p>
      </div>
    </div>
  );

  return (
    <div className={`min-h-screen transition-colors duration-200 ${t.bg}`}>
      <div className="max-w-7xl mx-auto px-4 md:px-8 py-6 md:py-10 space-y-5">

        {/* ── Header ── */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className={`text-2xl md:text-3xl font-bold tracking-tight ${t.text}`}>
              Banco de Brasília — BSLI4.SA
            </h1>
            <p className={`text-sm mt-1 ${t.textMuted}`}>
              {lang === 'en'
                ? 'Forensic timeline: Banco Master crisis · Mar 2025 – Mar 2026'
                : 'Timeline forense: crise do Banco Master · Mar 2025 – Mar 2026'}
            </p>
          </div>

          {/* Controls */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Language */}
            <div className={`flex rounded-lg border overflow-hidden text-xs font-medium ${t.border}`}>
              {['en','pt'].map(l => (
                <button key={l} onClick={() => setLang(l)}
                  className={`px-3 py-1.5 transition-colors ${lang === l ? t.toggleActive : t.toggleIdle}`}>
                  {l.toUpperCase()}
                </button>
              ))}
            </div>

            {/* Category filter */}
            <select value={filter} onChange={e => setFilter(e.target.value)}
              className={`text-xs border rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 ${t.border} ${t.inputBg} ${t.text}`}>
              {categories.map(c => (
                <option key={c} value={c}>
                  {c === 'all'
                    ? (lang === 'en' ? 'All categories' : 'Todas as categorias')
                    : (CATEGORY_LABELS[c]?.[lang] || c)}
                </option>
              ))}
            </select>

            {/* Dark mode */}
            <button onClick={() => setDark(d => !d)}
              className={`flex items-center gap-1.5 text-xs border rounded-lg px-3 py-1.5 transition-colors ${t.border} ${t.inputBg} ${t.text} ${t.surfaceHov}`}
              title={dark ? 'Switch to light mode' : 'Switch to dark mode'}>
              {dark ? '☀ Light' : '☾ Dark'}
            </button>
          </div>
        </div>

        {/* ── Stat chips ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: lang==='en'?'Peak price':'Preço máximo',   value:'R$ 12.49', sub:'31 Mar 2025', color:'text-green-500' },
            { label: lang==='en'?'Latest close':'Fechamento',    value:'R$ 4.21',  sub:'17 Mar 2026', color:'text-red-500'   },
            { label: lang==='en'?'Total decline':'Queda total',  value:'−66%',     sub:lang==='en'?'from peak':'do pico',color:'text-red-500'},
            { label: lang==='en'?'Key events':'Eventos-chave',   value:`${visibleEvents.length}`, sub:lang==='en'?'annotated':'anotados',color:'text-blue-400'},
          ].map((s,i) => (
            <div key={i} className={`rounded-xl border px-4 py-3 ${t.surface} ${t.border}`}>
              <div className={`text-xs mb-1 ${t.textFaint}`}>{s.label}</div>
              <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
              <div className={`text-xs mt-0.5 ${t.textFaint}`}>{s.sub}</div>
            </div>
          ))}
        </div>

        {/* ── Chart — full width ── */}
        <div className={`rounded-xl border p-4 md:p-6 ${t.surface} ${t.border}`}>
          <div className="flex flex-col lg:flex-row gap-6">
            <div className="lg:w-60">
              <div className={`rounded-xl border p-4 h-full ${t.border} ${t.surface}`}>
                <div className={`text-xs font-semibold uppercase tracking-wider mb-3 ${t.textFaint}`}>
                  {lang === 'en' ? 'Lines' : 'Linhas'}
                </div>
                <div className="flex flex-col gap-2">
                  {LINE_OPTIONS.map(option => {
                    const isActive = option.required || lineVisibility[option.key];
                    const status = option.required
                      ? (lang === 'en' ? 'Visible' : 'Ativo')
                      : isActive
                        ? (lang === 'en' ? 'Visible' : 'Visível')
                        : (lang === 'en' ? 'Hidden' : 'Oculta');
                    return (
                      <button
                        key={option.key}
                        type="button"
                        disabled={option.required}
                        aria-pressed={isActive}
                        onClick={() => { if (!option.required) toggleLineVisibility(option.key); }}
                        className={`flex items-center justify-between gap-3 px-3 py-2 rounded-lg border text-left transition ${t.border} ${t.surfaceHov} ${option.required ? 'cursor-default' : ''} ${isActive ? '' : 'opacity-60'}`}
                      >
                        <div className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: option.color }} />
                          <span className={`text-xs font-medium ${t.text}`}>
                            {option.label[lang]}
                          </span>
                        </div>
                        <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: isActive ? '#16a34a' : '#9ca3af' }}>
                          {status}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="flex-1">
              <div style={{ height: 520 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={marketData} margin={{ top: 16, right: 20, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={t.gridStroke} />

                <XAxis dataKey="Date" minTickGap={50}
                  tick={{ fill: t.axisColor, fontSize: 11 }} tickMargin={8}
                  tickFormatter={d => {
                    const [y,m] = d.split('-');
                    return `${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+m-1]} ${y.slice(2)}`;
                  }} />

                <YAxis yAxisId="price" orientation="left" domain={['auto','auto']}
                  tickFormatter={v => `R$${v.toFixed(0)}`}
                  tick={{ fill: t.axisColor, fontSize: 11 }} width={58} />

                <YAxis yAxisId="volume" orientation="right"
                  tickFormatter={v => v>=1000?`${(v/1000).toFixed(0)}k`:v}
                  tick={{ fill: t.axisColor, fontSize: 10 }} width={38} />

                <Tooltip content={<ChartTooltip dark={dark} />} />
                <Legend verticalAlign="top" height={34} iconType="circle"
                  wrapperStyle={{ fontSize: 12, color: dark ? '#94a3b8' : '#64748b' }} />

                {/* Volume bars */}
                <Bar yAxisId="volume" dataKey="Volume" name={lang==='en'?'Volume':'Volume'}
                  opacity={0.2} radius={[2,2,0,0]} isAnimationActive={false}>
                  {marketData.map((entry, i) => <Cell key={i} fill={volColor(entry)} />)}
                </Bar>

                {/* Event reference lines (pointer events disabled to keep dots clickable) */}
                {visibleEvents.map(ev => (
                  <ReferenceLine key={ev.date} yAxisId="price" x={ev.date}
                    stroke={CAT_COLOR[ev.category] || '#94a3b8'}
                    strokeWidth={activeDate === ev.date ? 2 : 1}
                    strokeDasharray="4 3"
                    opacity={activeDate === ev.date ? 0.85 : 0.3}
                    style={{ pointerEvents: 'none' }} />
                ))}

                {lineVisibility.SMA_30 && (
                  <Line yAxisId="price" type="monotone" dataKey="SMA_30" name="SMA 30"
                    stroke="#10b981" strokeWidth={1.5} dot={false} strokeDasharray="6 3" opacity={0.8} />
                )}
                {lineVisibility.SMA_7 && (
                  <Line yAxisId="price" type="monotone" dataKey="SMA_7" name="SMA 7"
                    stroke="#f59e0b" strokeWidth={1.5} dot={false} strokeDasharray="3 3" opacity={0.8} />
                )}

                {/* Price line with event dots */}
                <Line yAxisId="price" type="monotone" dataKey="Close"
                  name={lang==='en'?'Close':'Fechamento'}
                  stroke={dark ? '#e2e8f0' : '#0f172a'} strokeWidth={2}
                  dot={props => {
                    if (!eventDates.has(props.payload?.Date)) return null;
                    return (
                      <EventDot key={props.payload.Date} {...props}
                        events={visibleEvents}
                        onHover={handleHover}
                        onClickDot={handleClickDot}
                        activeDate={activeDate}
                        lockedDate={lockedEvent?.date} />
                    );
                  }}
                  activeDot={{ r: 5, fill: dark ? '#e2e8f0' : '#0f172a' }}
                  isAnimationActive={false} />

                <Brush dataKey="Date" height={30}
                  stroke={t.brushStroke} fill={t.brushFill}
                  travellerWidth={10} tickFormatter={() => ''} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Legend row */}
          <div className="flex flex-wrap gap-3 mt-4 pt-4" style={{ borderTop: `1px solid ${dark ? '#1e293b' : '#f1f5f9'}` }}>
            {Object.entries(CAT_COLOR).map(([cat, color]) => (
              <div key={cat} className="flex items-center gap-1.5 text-xs" style={{ color: dark ? '#94a3b8' : '#64748b' }}>
                <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: color }} />
                {CATEGORY_LABELS[cat]?.[lang] || cat}
              </div>
            ))}
            <div className={`text-xs ml-auto italic ${t.textFaint}`}>
              {lang === 'en' ? 'Click a marker to pin details' : 'Clique num marcador para fixar'}
            </div>
          </div>
            </div>
          </div>
        </div>

        {/* ── Event detail panel — below chart ── */}
        <div className={`rounded-xl border p-5 min-h-[120px] transition-all ${t.surface} ${t.border}`}>
          <div className={`text-xs font-semibold uppercase tracking-wider mb-4 ${t.textFaint}`}>
            {lang === 'en' ? 'Event details' : 'Detalhes do evento'}
          </div>
          <EventPanel
            event={activeEvent}
            lang={lang}
            locked={!!lockedEvent}
            onDismiss={handleDismiss}
            dark={dark}
          />
        </div>

        {/* ── Collapsible events table ── */}
        <div className={`rounded-xl border overflow-hidden ${t.surface} ${t.border}`}>
          {/* Toggle header */}
          <button
            onClick={() => setTableOpen(o => !o)}
            className={`w-full flex items-center justify-between px-5 py-4 text-left transition-colors ${t.surfaceHov}`}>
            <span className={`text-sm font-semibold ${t.text}`}>
              {lang === 'en' ? 'All annotated events' : 'Todos os eventos anotados'}
              <span className={`ml-2 text-xs font-normal ${t.textFaint}`}>({visibleEvents.length})</span>
            </span>
            <span className={`text-lg transition-transform duration-200 ${t.textMuted} ${tableOpen ? 'rotate-180' : ''}`}>
              ⌄
            </span>
          </button>

          {/* Collapsible body */}
          {tableOpen && (
            <div className="overflow-x-auto" style={{ borderTop: `1px solid ${dark ? '#1e293b' : '#f1f5f9'}` }}>
              <table className="w-full text-xs">
                <thead className={t.tableHead}>
                  <tr>
                    {['Date', 'Event', 'Category', 'Sentiment', 'BSLI4 Δ%', 'Price'].map(h => (
                      <th key={h} className={`text-left px-4 py-2.5 font-medium ${t.textMuted}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className={`divide-y ${t.borderDiv}`}>
                  {visibleEvents.map(ev => {
                    const sent = SENTIMENT_META[ev.sentiment];
                    const isActive = activeEvent?.date === ev.date;
                    return (
                      <tr key={ev.date}
                        className={`cursor-pointer transition-colors ${isActive ? t.activeRow : t.surfaceHov}`}
                        onMouseEnter={() => handleRowHover(ev)}
                        onMouseLeave={handleRowLeave}
                        onClick={() => handleRowClick(ev)}>
                        <td className={`px-4 py-2.5 font-mono whitespace-nowrap ${t.textMuted}`}>{ev.date}</td>
                        <td className={`px-4 py-2.5 max-w-xs ${t.text}`}>
                          {ev[`title_${lang}`] || ev.title_en}
                          {lockedEvent?.date === ev.date && (
                            <span className="ml-2 text-blue-400 text-xs">📌</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium"
                            style={{ background: CAT_COLOR[ev.category] + (dark ? '30' : '15'),
                                     color: CAT_COLOR[ev.category] }}>
                            {CATEGORY_LABELS[ev.category]?.[lang] || ev.category}
                          </span>
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="text-xs font-medium" style={{ color: sent.text }}>
                            {sent[lang]}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 font-mono font-medium whitespace-nowrap"
                          style={{ color: ev.bsli4_change_pct > 0 ? '#16a34a'
                                        : ev.bsli4_change_pct < 0 ? '#dc2626' : (dark ? '#64748b' : '#94a3b8') }}>
                          {ev.bsli4_change_pct != null
                            ? `${ev.bsli4_change_pct > 0 ? '+' : ''}${Number(ev.bsli4_change_pct).toFixed(2)}%`
                            : '—'}
                        </td>
                        <td className={`px-4 py-2.5 font-mono whitespace-nowrap ${t.textMuted}`}>
                          {ev.price_bsli4 != null ? `R$ ${Number(ev.price_bsli4).toFixed(2)}` : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <p className={`text-center text-xs pb-4 ${t.textFaint}`}>
          {lang === 'en'
            ? 'Data: B3 / Yahoo Finance · Events: RAG pipeline (Ollama + ChromaDB) · Extração e Preparação de Dados'
            : 'Dados: B3 / Yahoo Finance · Eventos: pipeline RAG (Ollama + ChromaDB) · Extração e Preparação de Dados'}
        </p>
      </div>
    </div>
  );
}