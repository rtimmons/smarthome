import { z } from "zod";

export const DayStatusSchema = z.enum(["past", "today", "future", "empty"]);

export const CalendarDaySchema = z.object({
  day: z.number().int().min(1).max(31).optional(),
  status: DayStatusSchema,
  label: z.string().optional()
});

export const CalendarWeekSchema = z.array(CalendarDaySchema).length(7);

export const CalendarMonthSchema = z.object({
  year: z.number().int(),
  month: z.number().int().min(1).max(12),
  month_label: z.string(),
  weeks: z.array(CalendarWeekSchema)
});

export const WeatherSchema = z.object({
  summary: z.string(),
  temperature_now_f: z.number(),
  temperature_high_f: z.number(),
  temperature_low_f: z.number(),
  feels_like_f: z.number(),
  wind_mph: z.number().optional(),
  wind_direction: z.string().optional(),
  chance_of_rain_pct: z.number().optional(),
  humidity_pct: z.number().optional(),
  aqi: z.number().optional(),
  uv_index: z.number().optional()
});

export const ScheduleEntrySchema = z.object({
  time: z.string(),
  title: z.string(),
  duration_minutes: z.number().optional(),
  location: z.string().optional(),
  source: z.string().optional()
});

export const ReminderSchema = z.string();

export const CommuteLegSchema = z.object({
  label: z.string(),
  duration_minutes: z.number(),
  traffic: z.string().optional(),
  route: z.string().optional(),
  notes: z.string().optional()
});

export const HabitSchema = z.object({
  label: z.string(),
  checked: z.boolean().default(false)
});

export const MetricsSchema = z.object({
  glucose_mg_dL: z.number().optional(),
  hydration_cups: z.number().optional()
});

export const SnapshotSchema = z.object({
  generated_at: z.string(),
  timezone: z.string(),
  today: z.object({
    iso_date: z.string(),
    weekday: z.string(),
    label: z.string()
  }),
  weather: WeatherSchema,
  calendar_month: CalendarMonthSchema,
  schedule: z.array(ScheduleEntrySchema),
  reminders: z.array(ReminderSchema),
  commute: z
    .object({
      legs: z.array(CommuteLegSchema)
    })
    .optional(),
  habits: z.array(HabitSchema).optional(),
  metrics: MetricsSchema.optional(),
  tips: z.array(z.string()).optional()
});

export type Snapshot = z.infer<typeof SnapshotSchema>;
