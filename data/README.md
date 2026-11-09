# Dati di Vice

Questa cartella contiene i dati usati da Vice. Registro completo delle licenze e motivazioni delle
scelte: [wiki/dati/fonti-e-licenze.md](../wiki/dati/fonti-e-licenze.md) e
[wiki/dati/fonti-fisiche.md](../wiki/dati/fonti-fisiche.md).

| Cartella | Contenuto | In git? |
|---|---|---|
| `raw/` | File scaricati dalle fonti originali dagli script in `scripts/` | **No** (gitignored): si riscaricano |
| `processed/` | Risultati piccoli elaborati da noi e letti dall'app (tabelle Parquet, JSON) | Sì |

Nel container la cartella è montata in `/app/data` (`VICE_DATA_DIR` per cambiarla).

Contenuto di `processed/`:
- `zenodo/`: `partite`, `sedute`, `carichi`, `giocatori` (Parquet, formato Vice) e `qualita.json`.
  Pipeline: [wiki/dati/pipeline-zenodo.md](../wiki/dati/pipeline-zenodo.md).
- `avvisi/taratura.json`: gli avvisi di Vice giorno per giorno su tutta la stagione, dalla taratura
  (`scripts/taratura_avvisi.py`, decisione 53; [wiki/metodi/avvisi.md](../wiki/metodi/avvisi.md)).
- `avvisi/archivio.json`: gli avvisi mostrati di ogni giorno di seduta, che l'app legge (decisione 54), con la
  firma del codice che li ha calcolati; si rifà con `scripts/prepara_avvisi.py`.
- `report/`: i report della seduta generati in anticipo da Vice (JSON, uno per giorno; decisione 49): testo
  scritto dal modello sui dati Zenodo, coi nomi di fantasia. Come si generano e si leggono:
  [wiki/tecnica/agente.md](../wiki/tecnica/agente.md#report-pronti-decisione-49).

`cache/` (gitignored) contiene file rigenerabili, per esempio gli export di seduta per le prove.

## Fonti e attribuzioni

### Zenodo 18986229: carico di allenamento e partita, stagione 2023/24

- **Autore:** Alejandro Rodríguez-Fernández. **Titolo sul repository:** *DATASETTMRatiosoccerseasson*
  (pubblicato il 12/03/2026). **DOI:** [10.5281/zenodo.18986229](https://doi.org/10.5281/zenodo.18986229).
  Articolo collegato: Sierra-Casas, Castillo, Clemente, Rodríguez-Fernández, *«Daily and
  Accumulated Training-to-Match Load Ratios in Professional Soccer: The Influence of Starting
  Status and Playing Position Across a Full Competitive Season»*, *Data* (MDPI) 2026, 11(4), 84,
  DOI [10.3390/data11040084](https://doi.org/10.3390/data11040084).
- **Licenza:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Modifiche apportate da Vice** (la CC BY chiede di indicarle; si completano in M1): conversione nel formato Vice,
  **nomi e numeri di maglia dei giocatori inventati** al posto dei codici anonimi, rapporti
  allenamento/partita ricalcolati. Dettaglio in `wiki/dati/pipeline-zenodo.md` (tappa M1).
- **Dicitura obbligatoria nell'app e nei report:** *«Nomi dei giocatori di fantasia; dati reali
  anonimi del dataset Zenodo 18986229 (Rodríguez-Fernández, CC BY 4.0).»*

Fino al 06/11/2026 Vice usava anche **SkillCorner Open Data** (20 partite di A-League 2024/25, licenza MIT) come riferimento esterno per le richieste della partita: tolto con la decisione 57, insieme ai suoi dati elaborati. Il lavoro fatto resta descritto in [wiki/dati/pipeline-skillcorner.md](../wiki/dati/pipeline-skillcorner.md).

## Regole

- Si aggiunge una fonte solo dopo averla registrata in
  [wiki/dati/fonti-e-licenze.md](../wiki/dati/fonti-e-licenze.md) con licenza verificata.
- Niente dati personali in `processed/` (niente date di nascita, niente nomi reali dei giocatori
  Zenodo).
