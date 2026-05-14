# MEMBRA Protocol

Membra_api is the system of record.

This repo follows the shared Membra protocol for campaign KPIs, owner engagement metrics, scan heatmaps, proof acceptance metrics, payout analytics, and advertiser performance reporting.

Core rule: KPI records are derived analytics, not canonical source-of-truth state.

Shared IDs: own_, adv_, ast_, cmp_, plc_, kit_, qr_, nfc_, proof_, scan_, tap_, pay_, pout_, aud_, snap_.

Analytics should preserve attribution to campaign, placement, asset, owner, proof event, scan/tap event, and payout state.
