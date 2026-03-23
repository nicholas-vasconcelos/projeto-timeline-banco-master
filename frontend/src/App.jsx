import React, { useState, useEffect } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Brush, ReferenceArea
} from 'recharts';

const App = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchMarketData = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/market-data/');
        if (!response.ok) throw new Error(`Backend API rejected request: ${response.status}`);
        const json = await response.json();
        if (!Array.isArray(json)) throw new Error(json.error || "Malformed data format.");
        setData(json);
      } catch (err) {
        console.error("Fetch error:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchMarketData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="text-lg font-semibold text-slate-600 animate-pulse">
          Loading contagion pipeline data...
        </div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50 p-4">
        <div className="bg-red-50 border-l-4 border-red-500 p-6 rounded-md shadow-sm max-w-2xl">
          <h2 className="text-xl font-bold text-red-700 mb-2">Connection Error</h2>
          <p className="text-red-600 mb-4">{error}</p>
          <p className="text-sm text-red-500">Ensure your Django server is running on port 8000 and CORS is configured correctly.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 md:p-10 max-w-7xl mx-auto">
      {/* Header Section */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
          Banco de Brasília (BSLI4.SA)
        </h1>
        <p className="text-slate-500 mt-2 text-sm md:text-base">
          Forensic Contagion Analysis: Banco Master Liquidation & Operação Compliance Zero
        </p>
      </div>
      
      {/* Chart Card */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 md:p-6">
        <div className="h-[600px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 20, right: 30, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis 
                dataKey="Date" 
                minTickGap={30} 
                tick={{ fill: '#64748b', fontSize: 12 }} 
                tickMargin={10} 
              />
              <YAxis 
                domain={['auto', 'auto']} 
                tickFormatter={(value) => `R$${value.toFixed(2)}`} 
                tick={{ fill: '#64748b', fontSize: 12 }} 
                width={80}
              />
              
              <Tooltip 
                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                formatter={(value, name) => [`R$ ${Number(value).toFixed(2)}`, name]}
                labelStyle={{ color: '#0f172a', fontWeight: 'bold', marginBottom: '4px' }}
              />
              <Legend verticalAlign="top" height={40} iconType="circle" wrapperStyle={{ fontSize: '14px', color: '#334155' }}/>
              
              {/* Event Zones */}
              <ReferenceArea x1="2025-11-01" x2="2025-11-30" fill="#fee2e2" fillOpacity={0.6} label={{ position: 'top', value: 'Banco Master Liq.', fill: '#ef4444', fontSize: 12, fontWeight: 'bold' }} />
              <ReferenceArea x1="2026-03-01" x2="2026-03-23" fill="#ffedd5" fillOpacity={0.6} label={{ position: 'top', value: 'Compliance Zero', fill: '#f97316', fontSize: 12, fontWeight: 'bold' }} />

              {/* Data Lines */}
              <Line type="monotone" dataKey="Close" name="Closing Price" stroke="#0f172a" strokeWidth={2.5} dot={false} activeDot={{ r: 6 }} />
              <Line type="monotone" dataKey="SMA_7" name="7-Day SMA" stroke="#f59e0b" strokeWidth={1.5} dot={false} strokeDasharray="5 5" />
              <Line type="monotone" dataKey="SMA_30" name="30-Day SMA" stroke="#10b981" strokeWidth={1.5} dot={false} />
              
              {/* Interactive Timeline */}
              <Brush dataKey="Date" height={40} stroke="#94a3b8" fill="#f8fafc" travellerWidth={12} tickFormatter={() => ''} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default App;