  readonly contextItems = computed(() => {
    const hasFilters = Object.keys(this.filters()).length > 0;
    let items: Row[] = hasFilters
      ? $fk_items_src
      : this.silo.items();
    const lf = this.localFilters();
    if (Object.values(lf).some(v => v))
      items = items.filter(item =>
        Object.entries(lf).every(([k, v]) => matchFilter((item as any)[k], v)));
    return items;
  });$contextual_new_count

  readonly displayItems = computed(() => {
    let items: Row[] = this.contextItems();$new_only_filter
    const sf = this.silo.sortField();
    if (sf) {
      const asc = this.silo.sortAsc();
      items = [...items].sort((a, b) => {
        const av = String((a as any)[sf] ?? '');
        const bv = String((b as any)[sf] ?? '');
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
    }
    return items;
  });