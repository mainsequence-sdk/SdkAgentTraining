A strong answer should include a snippet like this:

```text
mainsequence project jobs create --name "Vendor Prices - Nightly" --execution-path scripts/vendor_prices_launcher.py --related-image-id 77 --schedule-type crontab --schedule-expression "0 0 * * *"
```

It should also make these points explicit:
- Uses `project jobs create`
- Uses `--schedule-type crontab`
- Uses the requested schedule expression
- Includes `--related-image-id 77`
