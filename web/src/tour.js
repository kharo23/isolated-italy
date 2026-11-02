/** Stops of the guided tour. */

export const TOUR = [
  {
    title: "Italy, seen through five essentials",
    text: "Pharmacy, doctor or hospital, school, grocery, post office. Each hexagon shows how many are out of reach (more than 5 km).",
    center: [12.5, 42.0],
    zoom: 5.3,
    metric: "count",
    hold: 6500,
  },
  {
    title: "Two sources, two answers",
    text: "Each pharmacy source alone says about 535 thousand residents are far from one. They agree on only 159 thousand. Bright hexagons: the sources disagree.",
    center: [12.5, 42.0],
    zoom: 5.3,
    metric: "conflict",
    hold: 8000,
  },
  {
    title: "Where both sources agree",
    text: "Castelnuovo Berardenga, Chianti: the largest pharmacy gap that both sources agree on. Amazon Location computes the real trip and the 15-minute drive area.",
    center: [11.43177, 43.33951],
    zoom: 10.2,
    metric: "count",
    hold: 4500,
    click: true,
  },
  {
    title: "From a map of gaps to a plan",
    text: "Where would one new pharmacy help most residents? Greedy coverage, then each candidate is re-checked with a real 15-minute drive area.",
    center: [11.43177, 43.33951],
    zoom: 8.6,
    hold: 3000,
    sites: "pharmacy",
    site: 0,
  },
  {
    title: "Your turn",
    text: "Click anywhere, search a locality, change the threshold. Open data, Amazon Location Service, and a map that shows its own uncertainty.",
    center: [12.5, 42.0],
    zoom: 5.6,
    metric: "count",
    hold: 5000,
  },
];
