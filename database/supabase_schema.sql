-- supabase_schema.sql

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create potholes table
CREATE TABLE IF NOT EXISTS public.potholes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lat FLOAT NOT NULL,
    lng FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    detection_count INT NOT NULL DEFAULT 1,
    miss_count INT NOT NULL DEFAULT 0,
    last_detected TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'RESOLVED'))
);

-- Create detections_log table
CREATE TABLE IF NOT EXISTS public.detections_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pothole_id UUID NOT NULL REFERENCES public.potholes(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    detected BOOLEAN NOT NULL
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_potholes_status ON public.potholes(status);
CREATE INDEX IF NOT EXISTS idx_potholes_lat_lng ON public.potholes(lat, lng);
CREATE INDEX IF NOT EXISTS idx_detections_log_pothole_id ON public.detections_log(pothole_id);

-- Optional: RLS (Row Level Security) policies
-- For MVP, we allow public access (anon key will have full access).
ALTER TABLE public.potholes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.detections_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access to potholes" ON public.potholes FOR SELECT USING (true);
CREATE POLICY "Allow public insert access to potholes" ON public.potholes FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update access to potholes" ON public.potholes FOR UPDATE USING (true);

CREATE POLICY "Allow public read access to detections_log" ON public.detections_log FOR SELECT USING (true);
CREATE POLICY "Allow public insert access to detections_log" ON public.detections_log FOR INSERT WITH CHECK (true);

-- Helpful RPC (Remote Procedure Call) for finding nearby potholes to avoid fetching all in python
-- Uses the Haversine formula
CREATE OR REPLACE FUNCTION get_nearby_potholes(
    user_lat FLOAT,
    user_lng FLOAT,
    radius_meters FLOAT
) RETURNS SETOF public.potholes AS $$
DECLARE
    earth_radius_m CONSTANT FLOAT := 6371000;
BEGIN
    RETURN QUERY
    SELECT *
    FROM public.potholes
    WHERE status = 'ACTIVE' AND (
        earth_radius_m * acos(
            cos(radians(user_lat)) * cos(radians(lat)) *
            cos(radians(lng) - radians(user_lng)) +
            sin(radians(user_lat)) * sin(radians(lat))
        )
    ) <= radius_meters;
END;
$$ LANGUAGE plpgsql;
