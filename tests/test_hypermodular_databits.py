from membra_kpi.hypermodular_databits import (
    build_databit_tranches,
    build_hypermodular_sentence_backing,
    calculate_sentence_backing_score,
    create_databits_for_sentence,
)
from membra_kpi.sentence_as_service import build_sentence_product



def test_databits_created_for_sentence():
    sentence = build_sentence_product({"title": "MEMBRA sentence", "description": "Dense data-backed sentence."})
    databits = create_databits_for_sentence(sentence)
    assert len(databits) >= 5
    assert all(bit["databit_id"].startswith("dbit_") for bit in databits)



def test_tranches_created():
    sentence = build_sentence_product({"title": "MEMBRA sentence", "description": "Dense data-backed sentence."})
    databits = create_databits_for_sentence(sentence)
    tranches = build_databit_tranches(sentence, databits)
    assert len(tranches) >= 1
    assert all(t["tranche_id"].startswith("dbtr_") for t in tranches)



def test_sentence_backing_packet():
    packet = build_hypermodular_sentence_backing(
        listing={
            "listing_id": "lst_backing_1",
            "title": "Transit activation zone",
            "description": "Transit-adjacent activation inventory.",
        }
    )
    assert packet["sentence_backing_score"]["backing_score"] > 0
    assert len(packet["databits"]) > 0
    assert len(packet["databit_tranches"]) > 0
    assert packet["solana_scatter_anchor_plan"]["network"] == "solana-devnet"
