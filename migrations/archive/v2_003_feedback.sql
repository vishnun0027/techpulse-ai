-- migrations/v2_003_feedback.sql

CREATE TABLE IF NOT EXISTS user_feedback (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  article_id  uuid NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  signal      text NOT NULL CHECK (signal IN (
                  'clicked','saved','dismissed','more_like_this','less_like_this'
               )),
  created_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE user_feedback ENABLE ROW LEVEL SECURITY;
CREATE POLICY "user_feedback_policy" ON user_feedback
  FOR ALL USING (auth.uid() = user_id);

CREATE INDEX idx_feedback_user_signal ON user_feedback(user_id, signal);
