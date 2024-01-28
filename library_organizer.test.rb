# frozen_string_literal: true
# typed: strict

require "minitest/autorun"
require "minitest/reporters"

require_relative("./library_organizer")

Minitest::Reporters.use! [Minitest::Reporters::DefaultReporter.new(color: true)]

extend T::Sig # rubocop:disable Style/MixinUsage

describe "LibraryOrganizer" do
  before do
    @dir = T.let(Pathname.new(Dir.mktmpdir), Pathname)
    @watch = T.let(@dir / "watch", Pathname)
    @watch.mkdir(0o700)
    @library = T.let(@dir / "library", Pathname)
    @library.mkdir(0o700)
  end

  after do
    FileUtils.remove_dir(@dir, true)
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
  end
end
