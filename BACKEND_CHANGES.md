# Backend Integration Specification: TechPulse Pro UI 2.0

To support the high-density dashboard and the redesigned settings page, the following updates are required in the backend pipeline (Collector, Summarizer, and Delivery services).

---

## 1. Summarizer Service: Advanced Topic Filtering
The frontend now allows users to define three types of keywords instead of a single list.

### `app_config` Schema Update
- **Table**: `app_config`
- **Lookup**: `key = 'topics'`
- **Expected Value Structure**:
  ```json
  {
    "allowed": ["list", "of", "keywords"],
    "blocked": ["spam", "noise", "unrelated"],
    "priority": ["critical", "breaking", "priority"]
  }
  ```

### Required Logic Changes:
1. **Blocking**: Automatically discard any article where the title or snippet contains a token from the `blocked` list.
2. **Prioritization**: When calculating the relevance/intelligence score, add a **+20% boost** to any article containing a token from the `priority` list.
3. **Inclusion**: Continue using the `allowed` list as the primary filter for the initial gathering phase.

---

## 2. Telemetry Generation: Pipeline Metrics
The dashboard now displays real-time health and quality metrics. The backend must populate the `telemetry` table with these data points at the end of every processing run.

### Target Table: `telemetry`
| column       | type      | notes                                      |
|--------------|-----------|--------------------------------------------|
| `service`    | `text`    | Either `'collector'` or `'summarizer'`     |
| `metric_name`| `text`    | See below for specific names               |
| `value`      | `float8`  | The numeric measurement                    |
| `timestamp`  | `timestamptz` | Time of the run                         |

### Metrics to Implement:
1. **`noise_reduction`** (Reported by Summarizer):
   - Formula: `(Total Articles - Articles Summarized) / Total Articles * 100`
   - Goal: Higher is better (shows the AI is successfully filtering trash).
2. **`insight_quality`** (Reported by Summarizer):
   - Formula: Average relevance score of the summaries in the current batch.
3. **`source_health`** (Reported by Collector):
   - Formula: `(Successful RSS Fetches / Total Attempted) * 100`

---

## 3. Delivery Service: Multi-Channel Webhooks
The settings page now supports Discord in addition to Slack.

### `tenant_profiles` Data Retrieval
- **Table**: `tenant_profiles`
- **Fields to fetch**: `slack_webhook_url`, `discord_webhook_url`

### Required Logic Changes:
1. On every delivery run, check the `tenant_profiles` for the current user.
2. **Dual-Delivery**: If *both* URLs are set, the summary digest must be sent to both channels.
3. **Payload Formatting**: Ensure the Discord payload respects Discord's webhook API (which differs slightly from Slack's block kit).

---

## 4. User Identity (Supabase Auth)
- Ensure any user-facing notifications or audit logs use `user_metadata -> full_name` if available, falling back to the email prefix.
