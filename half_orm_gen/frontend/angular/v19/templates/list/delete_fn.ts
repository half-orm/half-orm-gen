
  handleDelete(id: string, e: Event): void {
    e.stopPropagation();
    if (confirm('Delete this item?')) {
      this.silo.remove(id).subscribe(() => this.silo.removeItem(String(id)));
    }
  }