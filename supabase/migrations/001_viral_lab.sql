-- Viral Lab: tablas para el sistema de contenido del Dr. John Bareño
-- Ejecutar en: Supabase Dashboard → SQL Editor (proyecto xfblbceaewcyeegjrylf)

-- 1. ADN del Dr. Bareño
CREATE TABLE IF NOT EXISTS bareno_dna (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  website_content TEXT,
  instagram_bio TEXT,
  instagram_top_captions TEXT,
  structured_dna JSONB,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Cuentas de competidores
CREATE TABLE IF NOT EXISTS bareno_competitors (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  handle TEXT UNIQUE NOT NULL,
  follower_count INTEGER,
  last_scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Posts virales scrapeados
CREATE TABLE IF NOT EXISTS bareno_viral_posts (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  competitor_id BIGINT REFERENCES bareno_competitors(id) ON DELETE CASCADE,
  apify_post_id TEXT,
  post_url TEXT,
  thumbnail_url TEXT,
  caption TEXT,
  likes INTEGER DEFAULT 0,
  views INTEGER DEFAULT 0,
  comments INTEGER DEFAULT 0,
  posted_at TIMESTAMPTZ,
  scraped_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Guiones generados
CREATE TABLE IF NOT EXISTS bareno_scripts (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_post_id BIGINT REFERENCES bareno_viral_posts(id),
  competitor_handle TEXT,
  surgery_type TEXT NOT NULL,
  original_caption TEXT,
  generated_script TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS: solo usuarios autenticados
ALTER TABLE bareno_dna ENABLE ROW LEVEL SECURITY;
ALTER TABLE bareno_competitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE bareno_viral_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE bareno_scripts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "auth_only" ON bareno_dna        FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "auth_only" ON bareno_competitors FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "auth_only" ON bareno_viral_posts FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "auth_only" ON bareno_scripts     FOR ALL USING (auth.role() = 'authenticated');
