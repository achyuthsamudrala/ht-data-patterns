.PHONY: serve build figures new-pattern check-symptoms check-interactions check-template clean

serve:
	mdbook serve --open

build:
	mdbook build

figures:
	@for sim in shuffle_cost_curve skew_straggler_impact spill_memory_curve \
	            vectorized_vs_rowwise_throughput backpressure_buffer_growth \
	            watermark_lateness_completeness compaction_write_amplification \
	            index_lookup_latency query_admission_wait; do \
	  echo "==> $$sim"; \
	  uv run python sims/$$sim/sim.py --out src/figures/$$sim; \
	done

new-pattern:
ifndef NAME
	$(error NAME is required. Usage: make new-pattern NAME=my-pattern [SECTION=joins-and-shuffle])
endif
	$(eval _SECTION := $(if $(SECTION),$(SECTION),))
	$(eval _DIR := $(if $(SECTION),src/patterns/$(SECTION),src/patterns))
	$(eval _DEST := $(_DIR)/$(NAME).md)
	@test ! -f $(_DEST) || (echo "Already exists: $(_DEST)"; exit 1)
	@mkdir -p $(_DIR)
	@cp templates/pattern.md $(_DEST)
	@echo "Created $(_DEST)"
	@echo "Remember to add it to src/SUMMARY.md"

check-symptoms:
	uv run python scripts/check_symptoms.py

check-interactions:
	uv run python scripts/check_interactions.py

check-template:
	uv run python scripts/check_template.py

clean:
	rm -rf book/
