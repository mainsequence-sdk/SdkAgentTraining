A strong answer should include a snippet like this:

```text
mainsequence project jobs create --name "Vendor Prices - Hourly" --execution-path scripts/vendor_prices_launcher.py --related-image-id 77 --schedule-type interval --schedule-every 1 --schedule-period hours
```

It should also make these points explicit:
- Uses `project jobs create`
- Uses `--schedule-type interval`
- Uses `--schedule-every 1 --schedule-period hours`
- Includes `--related-image-id 77`
