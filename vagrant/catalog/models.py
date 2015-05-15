from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    image_url = db.Column(db.String(255))

    # function converting into a dict for jsonify
    def toDict(self):
        return {
            'id': self.id,
            'name': self.name,
            'image_url': self.image_url
        }
    pass


class CatalogItem(db.Model):
    __tablename__ = 'catalog_item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    category = db.relationship('Category')

    # function converting into a dict for jsonify
    def toDict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'image_url': self.image_url,
            'category_id': self.category_id,
            'category': self.category.toDict()
        }
    pass
