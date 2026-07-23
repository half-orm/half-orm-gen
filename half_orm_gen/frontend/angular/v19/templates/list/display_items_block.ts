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
      const ft = this.fieldTypes[sf];
      items = [...items].sort((a, b) => {
        const av = (a as any)[sf];
        const bv = (b as any)[sf];
        if (av == null && bv == null) return 0;
        if (av == null) return asc ? -1 : 1;
        if (bv == null) return asc ? 1 : -1;
        let cmp: number;
        if (ft === 'number') {
          cmp = Number(av) - Number(bv);
        } else if (ft === 'date' || ft === 'datetime') {
          cmp = new Date(av).getTime() - new Date(bv).getTime();
        } else {
          cmp = String(av).localeCompare(String(bv));
        }
        return asc ? cmp : -cmp;
      });
    }
    return items;
  });