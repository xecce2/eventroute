export const mockPlans = {
  status: "ok",
  plans: [
    {
      id: "pl_001",
      labels: ["safest", "fastest"],
      train: {
        id: "tr_001",
        source: "fixture",
        fetched_at: "2026-10-03T09:40:00+02:00",
        mode: "train",
        category: "IC",
        train: "IC 6100",
        from: "Wrocław Główny",
        to: "Kraków Główny",
        dep: "2026-10-04T05:10:00+02:00",
        arr: "2026-10-04T08:15:00+02:00",
        price_pln: 64.0,
        changes: 0,
        delay_model: { p_on_time: 0.7, mean_delay_min: 6, p95_delay_min: 25 },
        known_delay_min: 0,
        url: "https://koleo.pl/rozklad-pkp/wroclaw-glowny/krakow-glowny/04-10-2026_04:00/all/all",
      },
      local_legs: [
        {
          mode: "tram",
          from: "Kraków Główny",
          to: "Tauron Arena",
          dep: "2026-10-04T08:25:00+02:00",
          arr: "2026-10-04T08:49:00+02:00",
          duration_min: 24,
          std_min: 4,
          line: "52",
        },
      ],
      venue_target: "2026-10-04T09:30:00+02:00",
      arrival_at_venue: "2026-10-04T08:50:00+02:00",
      buffer_min: 40,
      p_on_time: 0.93,
      price_pln: 64.0,
      overnight_stay: false,
      explanation: "Only direct IC that arrives before check-in.",
      buy_url: "https://koleo.pl",
    },
  ],
};

export const mockDisrupted = {
  notified: true,
  plans: [
    {
      ...mockPlans.plans[0],
      id: "pl_002",
      labels: ["safest"],
      buffer_min: 15,
      p_on_time: 0.55,
      arrival_at_venue: "2026-10-04T09:15:00+02:00",
      train: { ...mockPlans.plans[0].train, known_delay_min: 25 },
    },
  ],
};

export const mockCity = {
  event_id: "ev_hackyeah2026",
  participants_total: 420,
  arrivals_by_slot: [
    { slot: "2026-10-04T08:15:00+02:00", count: 60 },
    { slot: "2026-10-04T08:30:00+02:00", count: 112 },
    { slot: "2026-10-04T08:45:00+02:00", count: 140 },
    { slot: "2026-10-04T09:00:00+02:00", count: 70 },
  ],
  nodes: [
    {
      name: "Kraków Główny",
      lat: 50.0677,
      lon: 19.9479,
      peak_count: 140,
      peak_slot: "2026-10-04T08:45:00+02:00",
      load: "high",
    },
  ],
  origins: [{ station: "Warszawa Centralna", count: 150 }],
  recommendations: [
    { type: "add_trams", text: "Add tram 52 from 9:10 to 9:40", severity: "high" },
  ],
};
