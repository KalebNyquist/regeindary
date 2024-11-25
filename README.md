# Regeindary

## Description

The Regeindary tool is a means of importing publicly-available data from heterogeneous civil society and other organizational registries 
(for example, United States nonprofit records, the England and Wales charity register, United Nations recognized NGOs and
the B Corps directory) and putting them in a standardized form that is queryable in a MongoDB database. An "entity" (i.e. "organization")
may be linked to multiple "filings" (i.e. a 990 tax return or another form of "annual report").

*A note on naming: "Regeindary" is a loose portmanteau of the words "**reg**istr**y**" and "sta**ndar**d" that also evokes the terms 
"legendary", "repository", and "EIN" (as in ["Employer Identification Number"](https://en.wikipedia.org/wiki/Employer_Identification_Number)).*


## Progress and Roadmap

Because of each registry structures its data differently, each registry has a script unique to it for retrieving its data.
Each registry that already is or is planned to be a part of the Regeindary tool is listed below.
- [X] [Australia](scripts/Australia)
- [ ] B Corps
- [ ] Canada
- [X] [England and Wales](scripts/EnglandWales)
- [ ] Ireland
- [X] [New Zealand](scripts/NewZealand)
- [ ] Northern Ireland
- [ ] Norway
- [ ] United Nations Registered NGOs
- [ ] United States
  - [ ] Higher Education Institutions
  - [ ] IRS Registered Nonprofits


## Getting Started

### Dependencies

* [Python](https://www.python.org) (developing/testing on 3.12.4)
* [MongoDB](https://docs.mongodb.com/manual/installation/) (developing/testing on 8.0.0)
    * Recommended: [MongoDB Compass](https://www.mongodb.com/products/tools/compass)
      or [Studio 3T for MongoDB](https://studio3t.com) for graphically navigating the final product

### Installing

* After installing the above dependencies to your device, installing Regeindary should be as simple as downloading this
  repository

### Executing program (simple start)

* With `/scripts` as your working directory, run `interface.py`
* Select option `[2] Retrieve Registries` and select `[A] Run All` (you may be asked to select more)
* After completion, select `[4] Match Filings with Entities`

## Structure

* The `/schemas` folder contains [JSON Schema](https://json-schema.org) files that define how entities and filings for those entities are to be organized.
* The `/scripts` folder contains the Python code that operates Regeindary. Each subdirectory contains customized code for a specific registry, and a `mapping.json` file provides guidance on how to match fields and values from the original data into the aggregated target database.

## Authors

Kaleb Nyquist ([LinkedIn](https://www.linkedin.com/in/kalebnyquist/), [GitHub](https://github.com/KalebNyquist), [Twitter](https://x.com/KalebNyquist), Website)

## Version History

Placeholder

## License

Placeholder

## Acknowledgments

Placeholder
