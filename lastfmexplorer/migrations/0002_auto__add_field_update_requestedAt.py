# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Update.requestedAt'
        db.add_column('lastfmexplorer_update', 'requestedAt',
                      self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, default=datetime.datetime(2012, 10, 20, 0, 0), blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'Update.requestedAt'
        db.delete_column('lastfmexplorer_update', 'requestedAt')


    models = {
        'lastfmexplorer.album': {
            'Meta': {'unique_together': "(('artist', 'title'),)", 'object_name': 'Album'},
            'artist': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['lastfmexplorer.Artist']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'title': ('twothreefall.lastfmexplorer.models.TruncatingCharField', [], {'max_length': '100'})
        },
        'lastfmexplorer.artist': {
            'Meta': {'object_name': 'Artist'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('twothreefall.lastfmexplorer.models.TruncatingCharField', [], {'unique': 'True', 'max_length': '75'})
        },
        'lastfmexplorer.artisttags': {
            'Meta': {'unique_together': "(('artist', 'tag'),)", 'object_name': 'ArtistTags'},
            'artist': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['lastfmexplorer.Artist']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'score': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'tag': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['lastfmexplorer.Tag']"})
        },
        'lastfmexplorer.tag': {
            'Meta': {'unique_together': "(('tag',),)", 'object_name': 'Tag'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'tag': ('twothreefall.lastfmexplorer.models.TruncatingCharField', [], {'max_length': '100'})
        },
        'lastfmexplorer.track': {
            'Meta': {'unique_together': "(('artist', 'title'),)", 'object_name': 'Track'},
            'artist': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['lastfmexplorer.Artist']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'title': ('twothreefall.lastfmexplorer.models.TruncatingCharField', [], {'max_length': '100'})
        },
        'lastfmexplorer.update': {
            'Meta': {'object_name': 'Update'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'requestedAt': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'type': ('django.db.models.fields.IntegerField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['lastfmexplorer.User']"}),
            'week_idx': ('django.db.models.fields.PositiveSmallIntegerField', [], {})
        },
        'lastfmexplorer.user': {
            'Meta': {'ordering': "['username']", 'unique_together': "(('username',),)", 'object_name': 'User'},
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'last_seen': ('django.db.models.fields.DateField', [], {'auto_now': 'True', 'blank': 'True'}),
            'last_updated': ('django.db.models.fields.DateField', [], {}),
            'registered': ('django.db.models.fields.DateField', [], {}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '15'})
        },
        'lastfmexplorer.weekdata': {
            'Meta': {'unique_together': "(('user', 'week_idx', 'artist'),)", 'object_name': 'WeekData'},
            'artist': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['lastfmexplorer.Artist']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plays': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'rank': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['lastfmexplorer.User']"}),
            'week_idx': ('django.db.models.fields.PositiveSmallIntegerField', [], {'db_index': 'True'})
        },
        'lastfmexplorer.weekswithsyntaxerrors': {
            'Meta': {'object_name': 'WeeksWithSyntaxErrors'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['lastfmexplorer.User']"}),
            'week_idx': ('django.db.models.fields.PositiveSmallIntegerField', [], {'db_index': 'True'})
        },
        'lastfmexplorer.weektrackdata': {
            'Meta': {'unique_together': "(('user', 'week_idx', 'track'),)", 'object_name': 'WeekTrackData'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plays': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'rank': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'track': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['lastfmexplorer.Track']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['lastfmexplorer.User']"}),
            'week_idx': ('django.db.models.fields.PositiveSmallIntegerField', [], {'db_index': 'True'})
        }
    }

    complete_apps = ['lastfmexplorer']