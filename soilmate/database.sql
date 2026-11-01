-- Create database first (run this separately if needed: CREATE DATABASE soilmate_db;)

CREATE TABLE IF NOT EXISTS soil_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    drainage VARCHAR(50),
    water_retention VARCHAR(50),
    common_ph_range VARCHAR(20),
    improvement_tips TEXT
);

CREATE TABLE IF NOT EXISTS crops (
    id SERIAL PRIMARY KEY,
    common_name VARCHAR(100) NOT NULL,
    local_name VARCHAR(100),
    category VARCHAR(50), 
    ph_min NUMERIC(3, 1),
    ph_max NUMERIC(3, 1),
    germination_days_min INT,
    germination_days_max INT,
    harvest_days_min INT,
    harvest_days_max INT,
    ideal_planting_season VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS crop_soil_compatibility (
    crop_id INT REFERENCES crops(id) ON DELETE CASCADE,
    soil_type_id INT REFERENCES soil_types(id) ON DELETE CASCADE,
    PRIMARY KEY (crop_id, soil_type_id)
);

-- Insert all soil and surface profiles recognized by classes.json.
-- Keep the original three first so the sample compatibility ids below stay valid.
INSERT INTO soil_types (name, description, drainage, water_retention, common_ph_range, improvement_tips) VALUES
('Black Soil', 'Rich in organic matter and humus. Highly fertile, holds moisture well, and supports intense microbial activity.', 'Moderate / Good', 'High', '6.0 - 7.5', 'Maintain organic mulch annually. Minimal amendment needed; great for leafy greens.'),
('Red Soil', 'Iron-rich tropical soil, typically acidic and well-draining, but can pack down hard if dry.', 'Rapid / Good', 'Low to Moderate', '5.0 - 6.0', 'Incorporate agricultural lime to balance pH and mix in vermicast or compost to boost nutrient retention.'),
('Yellow Soil', 'Coarse-textured sandy/loamy soil. Highly porous, drains water very quickly, and leaches nutrients fast.', 'Rapid / High', 'Low', '5.5 - 7.0', 'Heavy addition of organic compost and manure is essential to prevent water and nutrient loss.'),
('Alluvial Soil', 'Fertile, silt-rich soil deposited by rivers and floods. Usually deep, moisture-retentive, and nutrient-rich, making it one of the best soils for Philippine lowland farming.', 'Moderate / Good', 'High', '5.5 - 7.0', 'Protect riverbank plots from erosion with cover crops or riprap. Open drainage channels during heavy rain, then side-dress with compost after floods leach nutrients. Avoid burning crop residue; incorporate it instead to keep organic matter high.'),
('Cinder Soil', 'Volcanic cinder or scoria soil. Coarse, highly porous, and fast-draining, with good mineral content but limited water and nutrient holding capacity.', 'Very Rapid / Excessive', 'Low', '5.5 - 7.0', 'Add compost, vermicast, and coconut coir to slow drainage and hold nutrients. Mulch heavily and water more often in small amounts. Cinder is excellent for raised beds and drought-tolerant crops; apply lime if the soil is strongly acidic.'),
('Clay Soil', 'Heavy, fine-textured soil made of very small particles. Sticky when wet and hard or cracked when dry; drains slowly but holds water and nutrients well.', 'Slow / Poor', 'Very High', '5.5 - 7.0', 'Avoid tilling when wet to prevent compaction. Add coarse sand, rice hull, compost, and aged manure to improve structure. Plant on raised beds, keep drainage channels clear, and choose water-tolerant crops such as rice, taro, and kangkong during the wet season.'),
('Laterite Soil', 'Iron- and aluminium-rich tropical soil, often reddish and gravelly. Acidic, low in nutrients, and prone to hardening when exposed, but suitable for hardy upland crops.', 'Rapid / Good', 'Low to Moderate', '4.5 - 6.0', 'Apply agricultural lime to raise pH and add generous compost or manure. Keep the soil covered with mulch or cover crops to stop laterite from baking hard. Grow acid-tolerant crops such as cassava, sweet potato, peanut, ginger, and ube.'),
('Peat Soil', 'Dark, spongy soil formed from partly decomposed plant material. Very high in organic matter but acidic, waterlogged, and low in available nutrients.', 'Very Poor / Waterlogged', 'Excessive', '4.0 - 5.5', 'Open shallow drainage ditches, but never drain peat completely - dry peat burns easily and subsides. Apply lime to reduce acidity, then add compost and rock phosphate. Grow acid-tolerant, water-loving crops such as rice, taro, kangkong, and alugbati.'),
('Concrete Surface', 'Impervious, non-porous man-made urban surface. Natural in-ground root penetration is impossible.', 'None (Runoff)', 'None', 'N/A', 'Direct planting in the ground is not possible. Opt for container gardening, raised garden beds, hanging planters, or vertical wall gardens. For cracks or paver gaps, consider creeping groundcovers like Bermuda grass or dwarf carpet grass.'),
('Soil with Algae', 'Surface biocrust or green algal slime. Indicates severe waterlogging, high compaction, poor drainage, and heavy shade or high moisture saturation.', 'Very Poor / Waterlogged', 'Excessive', '5.0 - 6.5', 'Immediately reduce watering and aerate the topsoil by gentle tilling. Incorporate coarse sand, perlite, or organic compost to restore oxygen flow. Apply agricultural lime if moss or algae is driven by acidic damp conditions.')
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    drainage = EXCLUDED.drainage,
    water_retention = EXCLUDED.water_retention,
    common_ph_range = EXCLUDED.common_ph_range,
    improvement_tips = EXCLUDED.improvement_tips;

-- Insert Philippine Crops
INSERT INTO crops (common_name, local_name, category, ph_min, ph_max, germination_days_min, germination_days_max, harvest_days_min, harvest_days_max, ideal_planting_season) VALUES
('Bitter Gourd', 'Ampalaya', 'Fruiting', 6.0, 6.7, 5, 10, 60, 80, 'Dry Season (Oct - Feb) or Year-round with good drainage'),
('Eggplant', 'Talong', 'Fruiting', 5.5, 6.8, 7, 14, 80, 100, 'Dry Season (Oct - Jan) / Year-round'),
('Bok Choy / Pechay', 'Pechay', 'Leafy', 5.5, 7.0, 3, 5, 30, 45, 'Cool Dry Months (Nov - Feb) / Year-round'),
('String Beans', 'Sitaw', 'Legume', 5.5, 6.5, 4, 8, 50, 65, 'Dry to Late Wet Season (Oct - May)'),
('Cassava', 'Kamoteng Kahoy', 'Root', 5.0, 6.5, 7, 14, 240, 300, 'Start of Rainy Season (May - July)'),
('Sweet Potato', 'Kamote', 'Root', 5.5, 6.5, 7, 10, 90, 120, 'Year-round (Best planted near end of rainy season)');

-- Map compatibility to our 3 Soil Types
-- 1: Black Soil, 2: Red Soil, 3: Yellow Soil
INSERT INTO crop_soil_compatibility (crop_id, soil_type_id) VALUES
(1, 1), (1, 3), -- Ampalaya in Black, Yellow
(2, 1), (2, 2), -- Talong in Black, Red
(3, 1),         -- Pechay in Black Soil
(4, 1), (4, 3), -- Sitaw in Black, Yellow
(5, 2), (5, 3), -- Kamoteng Kahoy in Red, Yellow
(6, 2), (6, 3); -- Kamote in Red, Yellow

-- ----------------- PLANTING CALENDAR -----------------
-- Structured months so "what can I plant this month?" can be answered by query
-- instead of by parsing ideal_planting_season text.
CREATE TABLE IF NOT EXISTS crop_planting_months (
    crop_id INT NOT NULL REFERENCES crops(id) ON DELETE CASCADE,
    month SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
    PRIMARY KEY (crop_id, month)
);

CREATE INDEX IF NOT EXISTS idx_crop_planting_months_month
    ON crop_planting_months (month);

INSERT INTO crop_planting_months (crop_id, month)
SELECT c.id, m.month
FROM crops c
JOIN (VALUES
    ('Bitter Gourd', 10), ('Bitter Gourd', 11), ('Bitter Gourd', 12),
    ('Bitter Gourd', 1),  ('Bitter Gourd', 2),
    ('Eggplant', 10), ('Eggplant', 11), ('Eggplant', 12), ('Eggplant', 1),
    ('Bok Choy / Pechay', 11), ('Bok Choy / Pechay', 12),
    ('Bok Choy / Pechay', 1),  ('Bok Choy / Pechay', 2),
    ('String Beans', 10), ('String Beans', 11), ('String Beans', 12),
    ('String Beans', 1),  ('String Beans', 2),  ('String Beans', 3),
    ('String Beans', 4),  ('String Beans', 5),
    ('Cassava', 5), ('Cassava', 6), ('Cassava', 7),
    ('Sweet Potato', 1),  ('Sweet Potato', 2),  ('Sweet Potato', 3),
    ('Sweet Potato', 4),  ('Sweet Potato', 5),  ('Sweet Potato', 6),
    ('Sweet Potato', 7),  ('Sweet Potato', 8),  ('Sweet Potato', 9),
    ('Sweet Potato', 10), ('Sweet Potato', 11), ('Sweet Potato', 12)
) AS m(common_name, month)
  ON c.common_name = m.common_name
ON CONFLICT (crop_id, month) DO NOTHING;

-- ----------------- CROP CATALOG -----------------
-- Allows seed.py to upsert crops by name, so the catalog stays idempotent.
CREATE UNIQUE INDEX IF NOT EXISTS ux_crops_common_name ON crops (common_name);

-- The full catalog (35 crops with months and soil mapping) lives in
-- data/crops.json. After creating the database, load it with:
--     .venv/Scripts/python.exe seed.py

-- ----------------- SCAN & CHAT HISTORY -----------------
CREATE TABLE IF NOT EXISTS scans (
    id BIGSERIAL PRIMARY KEY,
    user_id INT,
    session_id VARCHAR(64),
    filename VARCHAR(255) NOT NULL,
    predicted_soil VARCHAR(50),
    confidence REAL,
    identified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scans_session
    ON scans (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scans_user
    ON scans (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chat_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INT,
    session_id VARCHAR(64),
    role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'bot')),
    message TEXT NOT NULL,
    intent VARCHAR(64),
    confidence REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_logs_session
    ON chat_logs (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_logs_user
    ON chat_logs (user_id, created_at DESC);

-- ----------------- USER ACCOUNTS -----------------
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_scans_user') THEN
        ALTER TABLE scans
            ADD CONSTRAINT fk_scans_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_chat_logs_user') THEN
        ALTER TABLE chat_logs
            ADD CONSTRAINT fk_chat_logs_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;