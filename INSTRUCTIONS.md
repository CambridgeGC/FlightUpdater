# FlightUpdater Instructions

This program is intended to help check the log in Gliding App, identify any errors and then upload it to Aerolog.
Errors should be fixed in Gliding App before the upload (this is important - Gliding App is our main log)

## Fetch and Compare

- Use **Fetch and Compare** to load flights from Gliding App for a particular day and compare them with Ktrax and Aerolog:
- The **Modify Payer** button will change the payer for trial and scout flights to an appropriate account number.

## List and print

You can print the Gliding App list either to a printer or to a file

## Aerolog Upload

The Aerolog upload normally includes Gliding.App flights departing from GRL. It won't include any arrivals.

- If **Also upload non-GRL club departures** is ticked, club aircraft departing from other airfields are also included. Since we would normally charge for these, this should be the default
- If **Dryrun only** is ticked, no flights are sent to Aerolog.
- If **Show JSON** is ticked, the Aerolog payload JSON is displayed during dry-run.

## Aircraft

Flights which will be uploaded to Aerolog need to have their aircraft in the Aerolog Aircraft table. We can't yet access this through an API, but we can export it to an excel file. Use **Load Aerolog Aircraft** to load the Aerolog aircraft spreadsheet into the cache.

Use **Compare Aircraft** to compare Gliding.App aircraft against the Aerolog aircraft cache.
