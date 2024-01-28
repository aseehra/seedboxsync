# frozen_string_literal: true
# typed: strict

require "minitest/autorun"
require "minitest/reporters"

require_relative("./library_organizer")

Minitest::Reporters.use! [Minitest::Reporters::DefaultReporter.new(color: true)]

extend T::Sig # rubocop:disable Style/MixinUsage

describe "LibraryOrganizer" do
  before do
    @tmpdir = T.let(Pathname.new(Dir.mktmpdir), Pathname)
    @watch = T.let(@tmpdir / "watch", Pathname)
    @watch.mkdir(0o700)
    @library = T.let(@tmpdir / "library", Pathname)
    @library.mkdir(0o700)
  end

  after do
    FileUtils.remove_dir(@tmpdir, true)
  end

  describe "#parse_series" do
    it "parses normal sXXeXX formatted names" do
      path = Pathname.new("/home/arun/star.trek.strange.new.worlds.s01e02.mkv")
      result = LibraryOrganizer.new(@library).series_name(path)
      assert_equal(Pathname.new("star trek strange new worlds"), result)
    end

    it "parses normal SSxEE formatted names" do
      path = Pathname.new("/home/arun/star.trek.strange.new.worlds.1x02.mkv")
      result = LibraryOrganizer.new(@library).series_name(path)
      assert_equal(Pathname.new("star trek strange new worlds"), result)
    end
  end

  describe "on file create" do
    it "creates a link to the new location" do
      original = @watch / "Star.Trek.Strange.New.Worlds.S01E01.mkv"

      organizer = LibraryOrganizer.new(@library)
      organizer.watch([@watch])

      original.open("w") do |file|
        file.write("test")
      end

      organizer.process

      expected_dir = @library / "star trek strange new worlds"
      assert(expected_dir.directory?)
      expected_file = expected_dir / original.basename
      assert(expected_file.file?)
    end

    it "only creates links for mp4 and mkv files" do
      original = @watch / "Star.Trek.Strange.New.Worlds.S01E01.jpg"

      organizer = LibraryOrganizer.new(@library)
      organizer.watch([@watch])

      original.open("w") do |file|
        file.write("test")
      end

      organizer.process

      expected_dir = @library / "star trek strange new worlds"
      refute(expected_dir.directory?)
    end
  end

  describe "on file delete" do
    before do
      @series_dir = T.let(@library / "star trek strange new worlds", Pathname)
      @series_dir.mkdir(0o700)

      @episodes = T.let([
        @watch / "Star.Trek.Strange.New.Worlds.S01E01.mkv",
        @watch / "Star.Trek.Strange.New.Worlds.1x02.mp4"
      ], T::Array[Pathname])

      @episodes.each do |e|
        e.open("w") do |f|
          f.write("test")
        end
        (@series_dir / e.basename).open("w") do |f|
          f.write("test")
        end
      end
    end

    it "deletes the library link if multiple things exist in the library" do
      organizer = LibraryOrganizer.new(@library)
      organizer.watch([@watch])

      episode = T.must(@episodes.first)
      episode.delete

      organizer.process

      refute((@series_dir / episode.basename).exist?)
    end

    it "delete the series directory if no more files exist" do
      organizer = LibraryOrganizer.new(@library)
      organizer.watch([@watch])

      @episodes.each(&:delete)

      organizer.process

      refute(@series_dir.exist?)
    end
  end
end
