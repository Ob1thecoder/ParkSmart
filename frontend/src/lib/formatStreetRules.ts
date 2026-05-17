import type { RestrictionRule, ZoneSegment } from "../types";

export type ParsedRule = {
  type: "no_stopping" | "no_parking" | "timed" | "loading" | "permit_only" | "other";
  label: string;
  times: string;
  days: string;
  note?: string;
};

function formatTime(t: string): string {
  const match = t.match(/^(\d{1,2}):?(\d{2})?\s*(a|p|am|pm)?$/i);
  if (!match) return t;
  
  let hour = parseInt(match[1], 10);
  const min = match[2] || "00";
  const meridiem = (match[3] || "").toLowerCase();
  
  let suffix = "AM";
  if (meridiem.startsWith("p")) {
    suffix = "PM";
  } else if (meridiem.startsWith("a")) {
    suffix = "AM";
  } else if (hour >= 12) {
    suffix = "PM";
  }
  
  if (hour === 0) hour = 12;
  else if (hour > 12) hour -= 12;
  
  return min === "00" ? `${hour} ${suffix}` : `${hour}:${min} ${suffix}`;
}

function formatDayAbbrev(d: string): string {
  const map: Record<string, string> = {
    m: "Mon", mo: "Mon", mon: "Mon", monday: "Mon",
    t: "Tue", tu: "Tue", tue: "Tue", tuesday: "Tue",
    w: "Wed", we: "Wed", wed: "Wed", wednesday: "Wed",
    th: "Thu", thu: "Thu", thursday: "Thu",
    f: "Fri", fr: "Fri", fri: "Fri", friday: "Fri",
    s: "Sat", sa: "Sat", sat: "Sat", saturday: "Sat",
    su: "Sun", sun: "Sun", sunday: "Sun",
  };
  return map[d.toLowerCase()] || d;
}

function parseDays(text: string): string {
  if (!text || text.trim() === "") return "Every day";
  
  const t = text.trim().toUpperCase();
  
  if (t.includes("M-F") || t.includes("MON-FRI")) return "Mon – Fri";
  if (t.includes("M-SA") || t.includes("MON-SAT")) return "Mon – Sat";
  if (t.includes("EVERYDAY") || t.includes("ALL DAY")) return "Every day";
  
  const dayMatches = text.match(/\b(M|T|W|Th|F|Sa|Su|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b/gi);
  if (dayMatches && dayMatches.length > 0) {
    const formatted = dayMatches.map(formatDayAbbrev);
    const unique = [...new Set(formatted)];
    if (unique.length === 7) return "Every day";
    if (unique.length === 5 && !unique.includes("Sat") && !unique.includes("Sun")) return "Mon – Fri";
    return unique.join(", ");
  }
  
  return "Every day";
}

function detectRuleType(text: string): ParsedRule["type"] {
  const t = text.toLowerCase();
  if (t.includes("no stopping")) return "no_stopping";
  if (t.includes("no parking")) return "no_parking";
  if (t.includes("loading")) return "loading";
  if (t.includes("permit")) return "permit_only";
  if (/\d+\s*(hr|hour|min|p)\b/i.test(t) || t.includes("timed")) return "timed";
  return "other";
}

function parseTimeRange(text: string): string {
  const timePattern = /(\d{1,2}):?(\d{2})?\s*(a|p|am|pm)?/gi;
  const times: string[] = [];
  let match;
  
  while ((match = timePattern.exec(text)) !== null) {
    times.push(match[0]);
  }
  
  if (times.length >= 2) {
    return `${formatTime(times[0])} – ${formatTime(times[1])}`;
  } else if (times.length === 1) {
    return `From ${formatTime(times[0])}`;
  }
  
  return "All hours";
}

function getRuleLabel(type: ParsedRule["type"], text: string): string {
  const timedMatch = text.match(/(\d+)\s*(hr|hour|p)\b/i);
  if (timedMatch && type === "timed") {
    const num = parseInt(timedMatch[1], 10);
    return `${num} Hour Parking`;
  }
  
  const minMatch = text.match(/(\d+)\s*min/i);
  if (minMatch && type === "timed") {
    return `${minMatch[1]} Minute Parking`;
  }
  
  const labels: Record<ParsedRule["type"], string> = {
    no_stopping: "No Stopping",
    no_parking: "No Parking",
    timed: "Timed Parking",
    loading: "Loading Zone",
    permit_only: "Permit Required",
    other: "Restriction",
  };
  return labels[type];
}

function extractNote(text: string): string | undefined {
  if (text.toLowerCase().includes("street sweeping")) return "Street sweeping";
  if (text.toLowerCase().includes("taxi")) return "Taxi zone";
  if (text.toLowerCase().includes("bus")) return "Bus zone";
  if (text.toLowerCase().includes("meter")) return "Metered";
  return undefined;
}

export function parseRuleText(text: string): ParsedRule {
  const type = detectRuleType(text);
  return {
    type,
    label: getRuleLabel(type, text),
    times: parseTimeRange(text),
    days: parseDays(text),
    note: extractNote(text),
  };
}

export function plainEnglishToBullets(text: string): ParsedRule[] {
  const t = text.trim();
  if (!t) return [];

  const ruleKeywords = /\b(No Parking|No Stopping|Loading Zone|Timed Parking|Permit Only|Street Sweeping|Metered Parking):/gi;
  
  const matches: Array<{ index: number }> = [];
  let match;
  const regex = new RegExp(ruleKeywords.source, ruleKeywords.flags);
  
  while ((match = regex.exec(t)) !== null) {
    matches.push({ index: match.index });
  }

  const rules: ParsedRule[] = [];
  const seen = new Set<string>();

  if (matches.length > 1) {
    for (let i = 0; i < matches.length; i++) {
      const start = matches[i].index;
      const end = i < matches.length - 1 ? matches[i + 1].index : t.length;
      const ruleText = t.substring(start, end).trim().replace(/[.,]+$/, "");
      
      if (ruleText.length > 5) {
        const key = ruleText.toLowerCase().replace(/\s+/g, " ");
        if (!seen.has(key)) {
          seen.add(key);
          rules.push(parseRuleText(ruleText));
        }
      }
    }
  } else {
    const bySentence = t
      .split(/\.\s+|\n+/)
      .map((s) => s.replace(/\.$/, "").trim())
      .filter((s) => s.length > 5);
    
    for (const sentence of bySentence) {
      const key = sentence.toLowerCase().replace(/\s+/g, " ");
      if (!seen.has(key)) {
        seen.add(key);
        rules.push(parseRuleText(sentence));
      }
    }
  }

  if (rules.length === 0 && t.length > 5) {
    rules.push(parseRuleText(t));
  }

  return rules;
}

function formatStructuredRule(r: RestrictionRule): ParsedRule {
  const type = r.type;
  let label: string;
  
  if (type === "timed" && r.max_minutes != null) {
    const hours = r.max_minutes / 60;
    label = hours >= 1 ? `${Math.floor(hours)} Hour Parking` : `${r.max_minutes} Minute Parking`;
  } else {
    const labels: Record<typeof type, string> = {
      no_stopping: "No Stopping",
      no_parking: "No Parking",
      timed: "Timed Parking",
      permit_only: "Permit Required",
      loading: "Loading Zone",
      other: "Restriction",
    };
    label = labels[type];
  }
  
  let days: string;
  if (r.days.length === 0 || r.days.length === 7) {
    days = "Every day";
  } else if (r.days.length === 5 && !r.days.includes("Sat") && !r.days.includes("Sun")) {
    days = "Mon – Fri";
  } else if (r.days.length === 6 && !r.days.includes("Sun")) {
    days = "Mon – Sat";
  } else {
    days = r.days.join(", ");
  }
  
  return {
    type,
    label,
    times: `${formatTime(r.start)} – ${formatTime(r.end)}`,
    days,
  };
}

export function rulesForSegment(seg: ZoneSegment): ParsedRule[] {
  if (seg.rules_structured?.length) {
    return seg.rules_structured.map(formatStructuredRule);
  }
  return plainEnglishToBullets(seg.rules_plain_english);
}
