# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Artist'
        db.create_table('lastfmexplorer_artist', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('twothreefall.lastfmexplorer.models.TruncatingCharField')(unique=True, max_length=75)),
        ))
        db.send_create_signal('lastfmexplorer', ['Artist'])

        # Adding model 'Album'
        db.create_table('lastfmexplorer_album', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('artist', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['lastfmexplorer.Artist'])),
            ('title', self.gf('twothreefall.lastfmexplorer.models.TruncatingCharField')(max_length=100)),
        ))
        db.send_create_signal('lastfmexplorer', ['Album'])

        # Adding unique constraint on 'Album', fields ['artist', 'title']
        db.create_unique('lastfmexplorer_album', ['artist_id', 'title'])

        # Adding model 'Track'
        db.create_table('lastfmexplorer_track', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('artist', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['lastfmexplorer.Artist'])),
            ('title', self.gf('twothreefall.lastfmexplorer.models.TruncatingCharField')(max_length=100)),
        ))
        db.send_create_signal('lastfmexplorer', ['Track'])

        # Adding unique constraint on 'Track', fields ['artist', 'title']
        db.create_unique('lastfmexplorer_track', ['artist_id', 'title'])

        # Adding model 'User'
        db.create_table('lastfmexplorer_user', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=15)),
            ('registered', self.gf('django.db.models.fields.DateField')()),
            ('last_seen', self.gf('django.db.models.fields.DateField')(auto_now=True, blank=True)),
            ('last_updated', self.gf('django.db.models.fields.DateField')()),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('image', self.gf('django.db.models.fields.URLField')(max_length=200)),
        ))
        db.send_create_signal('lastfmexplorer', ['User'])

        # Adding unique constraint on 'User', fields ['username']
        db.create_unique('lastfmexplorer_user', ['username'])

        # Adding model 'Update'
        db.create_table('lastfmexplorer_update', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['lastfmexplorer.User'])),
            ('week_idx', self.gf('django.db.models.fields.PositiveSmallIntegerField')()),
            ('type', self.gf('django.db.models.fields.IntegerField')()),
            ('status', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal('lastfmexplorer', ['Update'])

        # Adding model 'WeekData'
        db.create_table('lastfmexplorer_weekdata', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['lastfmexplorer.User'])),
            ('week_idx', self.gf('django.db.models.fields.PositiveSmallIntegerField')(db_index=True)),
            ('artist', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['lastfmexplorer.Artist'])),
            ('plays', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('rank', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal('lastfmexplorer', ['WeekData'])

        # Adding unique constraint on 'WeekData', fields ['user', 'week_idx', 'artist']
        db.create_unique('lastfmexplorer_weekdata', ['user_id', 'week_idx', 'artist_id'])

        # Adding model 'WeekTrackData'
        db.create_table('lastfmexplorer_weektrackdata', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['lastfmexplorer.User'])),
            ('week_idx', self.gf('django.db.models.fields.PositiveSmallIntegerField')(db_index=True)),
            ('track', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['lastfmexplorer.Track'])),
            ('plays', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('rank', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal('lastfmexplorer', ['WeekTrackData'])

        # Adding unique constraint on 'WeekTrackData', fields ['user', 'week_idx', 'track']
        db.create_unique('lastfmexplorer_weektrackdata', ['user_id', 'week_idx', 'track_id'])

        # Adding model 'Tag'
        db.create_table('lastfmexplorer_tag', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('tag', self.gf('twothreefall.lastfmexplorer.models.TruncatingCharField')(max_length=100)),
        ))
        db.send_create_signal('lastfmexplorer', ['Tag'])

        # Adding unique constraint on 'Tag', fields ['tag']
        db.create_unique('lastfmexplorer_tag', ['tag'])

        # Adding model 'ArtistTags'
        db.create_table('lastfmexplorer_artisttags', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('artist', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['lastfmexplorer.Artist'])),
            ('tag', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['lastfmexplorer.Tag'])),
            ('score', self.gf('django.db.models.fields.PositiveSmallIntegerField')()),
        ))
        db.send_create_signal('lastfmexplorer', ['ArtistTags'])

        # Adding unique constraint on 'ArtistTags', fields ['artist', 'tag']
        db.create_unique('lastfmexplorer_artisttags', ['artist_id', 'tag_id'])

        # Adding model 'WeeksWithSyntaxErrors'
        db.create_table('lastfmexplorer_weekswithsyntaxerrors', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['lastfmexplorer.User'])),
            ('week_idx', self.gf('django.db.models.fields.PositiveSmallIntegerField')(db_index=True)),
        ))
        db.send_create_signal('lastfmexplorer', ['WeeksWithSyntaxErrors'])


    def backwards(self, orm):
        # Removing unique constraint on 'ArtistTags', fields ['artist', 'tag']
        db.delete_unique('lastfmexplorer_artisttags', ['artist_id', 'tag_id'])

        # Removing unique constraint on 'Tag', fields ['tag']
        db.delete_unique('lastfmexplorer_tag', ['tag'])

        # Removing unique constraint on 'WeekTrackData', fields ['user', 'week_idx', 'track']
        db.delete_unique('lastfmexplorer_weektrackdata', ['user_id', 'week_idx', 'track_id'])

        # Removing unique constraint on 'WeekData', fields ['user', 'week_idx', 'artist']
        db.delete_unique('lastfmexplorer_weekdata', ['user_id', 'week_idx', 'artist_id'])

        # Removing unique constraint on 'User', fields ['username']
        db.delete_unique('lastfmexplorer_user', ['username'])

        # Removing unique constraint on 'Track', fields ['artist', 'title']
        db.delete_unique('lastfmexplorer_track', ['artist_id', 'title'])

        # Removing unique constraint on 'Album', fields ['artist', 'title']
        db.delete_unique('lastfmexplorer_album', ['artist_id', 'title'])

        # Deleting model 'Artist'
        db.delete_table('lastfmexplorer_artist')

        # Deleting model 'Album'
        db.delete_table('lastfmexplorer_album')

        # Deleting model 'Track'
        db.delete_table('lastfmexplorer_track')

        # Deleting model 'User'
        db.delete_table('lastfmexplorer_user')

        # Deleting model 'Update'
        db.delete_table('lastfmexplorer_update')

        # Deleting model 'WeekData'
        db.delete_table('lastfmexplorer_weekdata')

        # Deleting model 'WeekTrackData'
        db.delete_table('lastfmexplorer_weektrackdata')

        # Deleting model 'Tag'
        db.delete_table('lastfmexplorer_tag')

        # Deleting model 'ArtistTags'
        db.delete_table('lastfmexplorer_artisttags')

        # Deleting model 'WeeksWithSyntaxErrors'
        db.delete_table('lastfmexplorer_weekswithsyntaxerrors')


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