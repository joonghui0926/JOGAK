# JOGAK Public Data Integration

## Official datasets

JOGAK keeps the existing curated 2D part images. Public data supplies provenance,
historical constraints, stories, and time-limited availability.

`DATA_GO_KR_API_KEY` is the default public-data service key. `TOURAPI_KEY`,
`CULTURE_DATA_KEY`, and `PATTERN_API_KEY` are optional overrides for cases where
a provider issues a separate key. If those overrides are empty, the backend uses
`DATA_GO_KR_API_KEY`.

### Korea Tourism Organization TourAPI

- Dataset: `15101578`, Korean Tourism Information Service
- Endpoint family: `https://apis.data.go.kr/B551011/KorService2`
- Search operation: `searchKeyword2`
- Request fields used by JOGAK:
  `serviceKey`, `MobileOS`, `MobileApp`, `keyword`, `pageNo`,
  `numOfRows`, `_type`, `arrange`, `contentTypeId`
- Response fields consumed:
  `contentid`, `title`, `addr1`, `mapx`, `mapy`, `firstimage`,
  `firstimage2`, `copyrightdivisioncode`
- JOGAK use: destination identity, coordinates, representative image, and source
  attribution.

### National Museum of Korea eMuseum

- Dataset: `15104964`
- Culture Portal catalog ID: `82`
- Format: JSON or XML LINK API
- Metadata described by the provider includes resource title, collection DB,
  subject classification, keywords, description, temporal scope, material,
  thumbnail, rights/copyright, institution, and resource location.
- JOGAK use: connect an existing part to an original heritage record and inject
  period, material, and institution into the image-generation constraints.

The Culture Portal issues the callable LINK API endpoint after an application is
approved. Store that exact URL in `CULTURE_EMUSEUM_API_URL`; do not scrape the
catalog page.

### Korean Traditional Pattern Service

- Dataset: `15138934`
- Provider: Korea Culture Information Service
- Format: XML
- Provider metadata includes pattern number/name, thumbnail, shape/type, period,
  holding institution, description, source object, and material.
- JOGAK use: connect pattern-related parts to their source motif and preserve its
  period and material identity during generation.

Store the approved endpoint in `CULTURE_PATTERN_API_URL`.

### National Museum Exhibition Integration

- Dataset: `15105220`
- Culture Portal catalog ID: `539`
- Format: JSON or XML LINK API
- Official endpoint shown by Culture Portal:
  `https://api.kcisa.kr/openapi/service/CNV/API_CNV_042/request`
- Provider metadata includes exhibition title/subtitle, period, description,
  image/video, fee, inquiry, and venue.
- Consumed fields include `publisher`, `collectionDb`, `creater`, `title`,
  `alternativeTitle`, `description`, `localId`, `url`, `subDescription`,
  `imageObject`, `videoObject`, `spatialCoverage`, `affiliation`, `charge`,
  `contactPoint`, and `period`.
- JOGAK use: link the destination's `season` part to an exhibition. Once a dated
  event record exists, the part unlocks only between `starts_at` and `ends_at`.

Store the approved endpoint in `CULTURE_EXHIBITION_API_URL`. If application is
blocked or no service key is available, put an exported `.json` or `.csv` file
under `data/public/exhibitions` or point `PUBLIC_DATA_EXHIBITION_FILE` to that
file. The repository includes a Culture Portal preview sample at
`data/public/exhibitions/museum_exhibitions_15105220_preview.json`; the live API
reports a larger total count, so replace the preview with a full export when one
is available.

## Storage

- `public_data_records`: normalized official records and their raw response.
- `part_public_data_links`: relation between an existing part and a heritage,
  pattern, or exhibition record.
- `culture_dna`: generation constraints derived from linked records.

Every record retains provider, dataset ID, external ID, source URL, license note,
fetch time, checksum, and the original response JSON.

## Sync

```bash
PUBLIC_DATA_SYNC_ENABLED=true npm run sync:public-data -- --destination-id national_museum_korea
PUBLIC_DATA_SYNC_ENABLED=true npm run sync:public-data -- --all
```

The app never invents provenance when no record is returned. Unmatched parts
remain usable but display `공공데이터 원본 연결 대기`.

## Official references

- TourAPI: https://www.data.go.kr/data/15101578/openapi.do
- eMuseum: https://www.data.go.kr/data/15104964/openapi.do
- Traditional patterns: https://www.data.go.kr/data/15138934/openapi.do
- Museum exhibitions: https://www.data.go.kr/data/15105220/openapi.do
