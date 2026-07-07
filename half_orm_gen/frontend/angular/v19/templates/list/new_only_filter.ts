
    if (this.showNewOnly()) {
      items = items.filter(item => this.silo.isNew(this.getPkId(item)));
    }