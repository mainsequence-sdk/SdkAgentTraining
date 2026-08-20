A strong answer should include a snippet like this:

```text
mainsequence project jobs create --name "Vendor Prices - One Time" --execution-path scripts/vendor_prices_launcher.py --related-image-id 77 --schedule-type crontab --schedule-expression "0 2 * * *" --schedule-start-time "2026-03-15T02:00:00Z" --schedule-one-off
```

It should also make these points explicit:
- Uses the documented one-off flags
- Includes schedule start time
- Includes `--schedule-one-off`
- Includes `--related-image-id 77`
