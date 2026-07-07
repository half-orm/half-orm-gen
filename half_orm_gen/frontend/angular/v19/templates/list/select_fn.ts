
  selectAndNavigate(id: string): void {
    this.silo.selectedId.set(id);
    this.router.navigate(['/ho_bo/$schema_name/$table_name', id]);
  }
